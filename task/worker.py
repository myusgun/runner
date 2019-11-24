# -*- coding: utf-8 -*-
import datetime
import httplib
import importlib
import inspect
import json
import logging
import logging.handlers
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib2

from BaseHTTPServer import HTTPServer
from BaseHTTPServer import BaseHTTPRequestHandler

import state

class Environment:
	ADDRESS = '192.168.0.34' # FIXME 'unsigned.kr'
	PORT    = 80
	EMAIL   = 'mailer@unsigned.kr'

	HYPERVISOR = None # set in main() function

	@staticmethod
	def exceptionToMailForm(e):
		taskMgr = TaskManager.getInstance()
		return {
			'from': Environment.EMAIL,
			'to': taskMgr.properties.get('email'),
			'subject': '[ERROR] {0}'.format(taskMgr.name),
			'content':
				'{0}\n\n'
				'------------------------------\n'
				'{1}'.format(str(e), traceback.format_exc())
		}

class Worker:
	def __init__(self, script, seq):
		try:
			# create singleton classes
			Logger.create(script, seq)
			TaskManager.create(script, seq)

			# instantiate
			self.logger     = Logger.getInstance()
			self.taskMgr    = TaskManager.getInstance()
			self.taskHelper = TaskHelper()
			self.event      = WaitEvent()
			self.lock       = threading.Lock()
			self.messaging  = Messaging(self.callHandler)

			# assign
			self.statement  = state.NONE
			self.released   = False
			self.outFile    = None
			self.repeat     = 0

			# lazy call
			self.taskMgr.load()

			# lazy instantiate for virtualization
			self.virtualization = Virtualization()
			self.backup = Backup()

		except Exception as e:
			self.logger.exception(e)
			self.changeState(state.ERROR, err=str(e))

			raise

	def checkMissingProperties(self):
		try:
			items = ['desc', 'author', 'email', 'platform', 'repeat', 'contOnErr', 'backup']

			missingItems = items[:]

			for item in items:
				if self.taskMgr.properties.has(item):
					missingItems.remove(item)

			# 'backup' is only for virtualization
			if 'backup' in missingItems and not self.virtualization.isRequired:
				missingItems.remove('backup')

			if missingItems:
				raise NotImplementedError('Properties{0} is missing'.format(missingItems))

			self.initAttributes(statement=state.NONE)

			return self

		except Exception as e:
			self.logger.exception(e)
			self.changeState(state.ERROR, err=str(e))
			self.emailException(e)

			raise

	def ready(self):
		try:
			self.initAttributes()

			if self.virtualization.isRequired:
				self.changeState(state.VIRTUALIZING)
				self.virtualization.attempt()
				self.changeState(state.VIRTUALIZED)

			else:
				self.changeState(state.READY)

			return self

		except Exception as e:
			self.logger.exception(e)
			self.changeState(state.ERROR, err=str(e))
			self.emailException(e)

			if self.virtualization.done:
				self.shutdown()

			raise

	def do(self):
		TASK_THREAD_JOIN_TIMEOUT = 3

		if self.virtualization.isRequired:
			return

		# register methods for threading
		callees = [
			self.messaging.server.serve_forever,
			self.runTask
		]

		# instantiate
		threads = [threading.Thread(target=callee) for callee in callees]

		# get method name
		regexMethodName = re.compile('<bound method ([^ ]+) .*>')
		getMethodName   = lambda method: regexMethodName.match(str(method)).groups()[0]

		# start
		for callee, thread in zip(callees, threads):
			thread.setDaemon(True)
			thread.start()
			self.logger.info('{0}() was started as a thread'.format(getMethodName(callee)))

		# join
		for callee, thread in zip(callees, threads):
			if callee == self.runTask:
				continue

			thread.join()
			self.logger.info('{0}() thread was joined'.format(getMethodName(callee)))

		# join task thread with timeout
		threads[callees.index(self.runTask)].join(TASK_THREAD_JOIN_TIMEOUT)
		self.logger.info('{0}() thread was joined'.format(getMethodName(self.runTask)))

		# especially wait if data is backing up
		self.backup.wait()

		# stop vm
		if self.virtualization.done:
			self.shutdown()

	def initAttributes(self, **kwargs):
		obj = {
			'state'      : kwargs.get('statement', state.INITIALIZING),
			'address'    : Misc.getIPAddressOfActivatedNIC(),
			'port'       : self.messaging.port,
			'desc'       : self.taskMgr.properties.get('desc'),
			'author'     : self.taskMgr.properties.get('author'),
			'email'      : self.taskMgr.properties.get('email'),
			'platform'   : self.taskMgr.properties.get('platform'),
			'repeat'     : self.taskMgr.properties.get('repeat'),
			'hidden'     : self.taskMgr.properties.get('hidden'),
			'cont-on-err': self.taskMgr.properties.get('contOnErr'),
			'autorun'    : self.taskMgr.properties.get('autorun'),
			'plugins'    : self.taskMgr.properties.get('plugins'),
		}
		obj.update(kwargs)

		Messaging.setAttributes(obj)

	def callHandler(self, msg):
		try:
			"""
			message format
			{
			"type": "control" or "user",
			"value": "data"
			}
			"""

			self.logger.info(msg)

			# set handler
			handlerMap = {
				# <message type>: <handler method or function>
				'control': self.handleControlMessage,
				'user': self.taskMgr.handler
			}

			obj     = Json.load(msg)
			msgType = obj['type']
			value   = obj['value']

			handler = handlerMap.get(msgType, None)
			if handler is None:
				raise Exception('{0}-message-handler-method does not specified'.format(msgType))

			ret = handler(value)
			if not ret:
				ret = {}

			return ret

		# stop by user
		except Stop as e:
			self.logger.info(str(e))
			self.release()

		# exception will be logged and ignored
		except Exception as e:
			self.logger.exception(e)
			return { '__except__': str(e) }

	def runTask(self, **kwargs):
		syntaxErrors = (NameError, SyntaxError)

		try:
			self.setTaskProperties()

			while self.isContinued():
				try:
					if self.statement == state.ERROR:
						self.changeState(state.WAITING)

						# take breath
						self.event.wait(60)

					else:
						self.changeState(state.RUNNING)

					self.callTask()

					if self.statement == state.STOP:
						raise Stop()

					# if virtualized, back up data to host
					if self.virtualization.done:
						self.changeState(state.BACKING_UP)
						self.backup.run()

					self.changeState(state.CONTINUING)

				# raised from instance of Process class by PN message
				except Stop as e:
					self.logger.info(str(e))
					break

				# task error
				# except syntax error of task-script
				except (Exception, syntaxErrors) as e:
					# back up before change-state to ERROR
					isStopped = self.statement == state.STOP

					self.logger.exception(e)
					self.changeState(state.ERROR, err=str(e))
					self.emailException(e)

					stopOnError   = not self.taskMgr.properties.get('contOnErr')
					isSyntaxError = isinstance(e, syntaxErrors)

					if stopOnError or isSyntaxError or isStopped:
						raise

					self.logger.info('continued on error')

				# take breath
				self.event.wait(1)

			if state.isInProgress(self.statement):
				self.changeState(state.DONE)

		except Exception as e:
			self.logger.exception(e)
			self.changeState(state.ERROR, err=str(e))
			self.emailException(e)

		finally:
			self.release()

	def setTaskProperties(self):
		self.taskMgr.properties.set('logger', self.logger)

		# mount for virtualization
		if self.virtualization.done:
			self.virtualization.mountSharedFolder()
			self.taskMgr.properties.set('mount', self.virtualization.getMountPath())

		# redirect stdout and stderr to file in normal-mode
		if not self.taskMgr.isStandalone:
			outFileName  = '{0}.stdout'.format(self.taskMgr.name)
			self.outFile = open(outFileName, 'wb+', 0)
			sys.stdout   = self.outFile
			sys.stderr   = self.outFile

	def getStringIntervalAsSeconds(self, repeat):
		regexTime  = re.compile(r'\d+:\d+')
		regexEvery = re.compile(r'every (\d+)([hm])')

		matched = None
		seconds = None

		# daily
		matched = regexTime.match(repeat)
		if matched:
			def getTomorrow(dailyTime):
				delta    = datetime.datetime.now() + datetime.timedelta(days=1)
				tomorrow = '%4d-%02d-%02d %s:00' % (delta.year, delta.month, delta.day, dailyTime)

				now      = datetime.datetime.now()
				nextTime = datetime.datetime.strptime(tomorrow, '%Y-%m-%d %H:%M:%S')
				interval = nextTime - now
				seconds  = interval.total_seconds()

				return seconds

			seconds = getTomorrow(repeat)

		# every interval
		matched = regexEvery.match(repeat)
		if matched:
			interval, unit = matched.groups()
			interval = int(interval)

			if unit == 'm':
				seconds = interval * 60
			elif unit == 'h':
				seconds = interval * 60 * 60
			else:
				pass

		return seconds

	def isContinued(self):
		properties = self.taskMgr.properties

		# check end of repetition
		if self.statement == state.STOP:
			return False

		# repetition rule does not specified
		if not properties.has('repeat'):
			return False

		# get repeat
		repeat = properties.get('repeat')

		# no-repeat
		if repeat is None:
			if self.repeat > 0:
				return False

		elif isinstance(repeat, str):
			if repeat.lower() == 'infinite':
				pass

			# wait
			else:
				seconds = self.getStringIntervalAsSeconds(repeat)
				if not seconds:
					return False

				self.changeState(state.WAITING)
				self.event.wait(seconds)

				# awaken by user's stop request
				if self.statement == state.STOP:
					return False

		elif isinstance(repeat, (int, long)):
			if repeat <= 0 or self.repeat >= repeat:
				return False

		self.repeat += 1

		return True

	def callTask(self):
		self.taskMgr.action(self.taskHelper.interface)

	def changeState(self, statement, msg=None, err=None):
		self.statement = statement
		Messaging.changeState(statement, msg, err)

	def release(self):
		with self.lock:
			if self.released:
				return

			self.logger.info('release')

			self.taskHelper.terminateProcesses()
			self.event.awake()

			if self.messaging.server is not None:
				self.messaging.server.shutdown()

			if self.outFile:
				self.outFile.close()

			self.released = True

	def handleControlMessage(self, msg):
		get = lambda key: msg[key] if key in msg else None

		statement = get('state')
		if statement == state.STOP:
			self.changeState(state.STOP)
			raise Stop()

	def emailException(self, e):
		mailForm = Environment.exceptionToMailForm(e)
		Messaging.request(Messaging.Type.SEND_MAIL, mailForm)

	def shutdown(self):
		cmd = 'shutdown'

		if Misc.isWindows():
			cmd += ' -s -t 0'
		else:
			cmd += ' /h now'

		self.logger.info(cmd)
		os.system(cmd)

class IAttribute:
	def __init__(self):
		self.module = None

	def setModule(self, module):
		self.module = module

	def get(self, attr):
		if self.has(attr):
			return getattr(self.module, attr)
		else:
			return None

	def has(self, attr):
		return hasattr(self.module, attr)

	def set(self, attr, value):
		setattr(self.module, attr, value)

class Properties(IAttribute):
	def __init__(self, properties):
		IAttribute.__init__(self)
		self.setModule(properties)

# singleton
class TaskManager(IAttribute):
	__instance = None

	def __init__(self, script, seq):
		if TaskManager.__instance:
			raise Exception('singleton')

		IAttribute.__init__(self)

		# import and instantiate
		script        = os.path.abspath(script)
		dirname       = os.path.dirname(script)
		basename      = os.path.basename(script)
		modulename, _ = os.path.splitext(basename)

		self.script  = basename
		self.name    = modulename
		self.dirname = dirname
		self.seq     = seq

		# TODO: working directory by seq. ...
		"""
		self.workdir = os.path.join(self.dirname, self.seq)
		"""
		self.workdir = self.dirname
		self.plugins = []

		self.module     = None
		self.properties = None
		self.action     = None
		self.handler    = None

	def setWorkspace(self):
		if not os.path.isdir(self.workdir):
			os.makedirs(self.workdir)

		os.chdir(self.workdir)

	def load(self):
		self.setWorkspace()

		sys.path.append(self.dirname)
		module = importlib.import_module(self.name)

		self.setModule(module)

		if not self.has('action'):
			raise NotImplementedError('action() function is not defined in {0}'.format(self.script))

		if not self.has('Property'):
			raise NotImplementedError('Property class is not defined in {0}'.format(self.script))

		# properties
		properties      = self.get('Property')
		self.properties = Properties(properties)

		plugins         = self.properties.get('plugins')
		self.plugins    = [TaskManager.Plugin(name) for name in plugins]

		# get functions
		self.action     = self.get('action')
		self.handler    = self.get('handler')

	@staticmethod
	def create(script, seq):
		if TaskManager.__instance is None:
			TaskManager.__instance = TaskManager(script, seq)

		return TaskManager.getInstance()

	@staticmethod
	def getInstance():
		if TaskManager.__instance is None:
			raise Exception('TaskManager is not created')

		return TaskManager.__instance

	@property
	def isStandalone(self):
		return self.seq == 'standalone'

	# inner-class
	class Plugin(IAttribute):
		def __init__(self, name):
			IAttribute.__init__(self)

			if not name:
				raise Exception('no plugin name')

			self.name = name

			self.download()

			module = importlib.import_module(name)
			self.setModule(module)

		def download(self):
			url  = 'http://{0}:{1}/api/plugin/{2}'.format(Environment.ADDRESS, Environment.PORT, self.name)
			path = os.path.abspath('{0}.py'.format(self.name))

			logger = Logger.getInstance()
			logger.info('downloading plugin: {0} => {1}'.format(url, path))

			Misc.download(url, path)

		def get(self):
			return self.module

class WaitEvent:
	class StopWatch:
		def __init__(self):
			self.begin = 0
			self.end   = 0

			self.reset()

		def reset(self):
			self.begin = time.time()

		def stop(self):
			self.end = time.time()

		def getElapsedTime(self):
			return self.end - self.begin

# class WaitEvent
	def __init__(self):
		self.logger = Logger.getInstance()
		self.event = threading.Event()
		self.stopWatch = WaitEvent.StopWatch()

	def wait(self, timeout=None):
		self.logger.info('waiting {0} seconds ...'.format(timeout))

		self.stopWatch.reset()
		self.event.wait(timeout)
		self.stopWatch.stop()

		self.reset()

		return self.stopWatch.getElapsedTime()

	def awake(self):
		callstack = inspect.stack()
		caller    = callstack[1]
		method    = caller[3]
		lineno    = caller[2]
		self.logger.info('awaken by [{0}]{1}()'.format(lineno, method))

		self.event.set()

	def reset(self):
		self.event.clear()

# singleton
class Logger:
	__instance = None

	def __init__(self, script, seq):
		if Logger.__instance:
			raise Exception('singleton')

		basename          = os.path.basename(script)
		self.taskName, _  = os.path.splitext(basename)
		self.logger       = logging.getLogger(self.taskName)

		# self.addLogHandler(logging.StreamHandler())

		logFile = '{0}@{1}.log'.format(os.path.splitext(script)[0], seq)
		handler = logging.handlers.TimedRotatingFileHandler(logFile, when='D', backupCount=15)
		self.addLogHandler(handler)

	def addLogHandler(self, handler):
		logFormat = '[%(asctime)-15s][%(lineno)04d][%(module)s][%(funcName)s] %(message)s'
		formatter = logging.Formatter(logFormat)

		handler.setFormatter(formatter)
		handler.setLevel(logging.DEBUG)

		self.logger.setLevel(logging.DEBUG)
		self.logger.addHandler(handler)

	@staticmethod
	def create(script, seq):
		if Logger.__instance is None:
			Logger.__instance = Logger(script, seq).logger

		return Logger.getInstance()

	@staticmethod
	def getInstance():
		if Logger.__instance is None:
			raise Exception('Logger is not created')

		return Logger.__instance

class Messaging:
	def __init__(self, handler):
		self.port   = Misc.getAvailablePort()
		self.server = Messaging.Server.create(self.port, handler)

	@staticmethod
	def request(type, body=None):
		taskName = TaskManager.getInstance().name
		seq      = TaskManager.getInstance().seq

		if type is Messaging.Type.SET_ATTRIBUTES:
			method, url = 'POST', '/api/{0}/{1}'.format(taskName, seq)
		elif type is Messaging.Type.SEND_MAIL:
			method, url = 'POST', '/api?mail'
		elif type is Messaging.Type.VIRTUALIZE:
			method, url = 'POST', '/api/{0}/{1}/run?virtualize'.format(taskName, seq)
		elif type is Messaging.Type.BACK_UP:
			method, url = 'POST', '/api/{0}/{1}/backup?from=vm'.format(taskName, seq)
		else:
			raise Exception('undefined messaging type')

		# request without custom header
		return Messaging.Client().request(method, url, body=body)

	@staticmethod
	def changeState(statement, msg=None, err=None):
		obj = {
			'state': statement
		}

		if msg is not None: obj['msg'] = msg
		if err is not None: obj['err'] = err

		Messaging.setAttributes(obj)

	@staticmethod
	def setAttributes(obj):
		Messaging.request(Messaging.Type.SET_ATTRIBUTES, body=obj)

	# inner-class
	class Type:
		SET_ATTRIBUTES = object()
		SEND_MAIL      = object()
		VIRTUALIZE     = object()
		BACK_UP        = object()

	"""
	# inner-class
	class Pool:
		__instance = None

		def __init__(self):
			self.event = WaitEvent()
			self.pool = []
			self.logger = Logger.getInstance()

		@staticmethod
		def getInstance():
			if Messaging.Pool.__instance is None:
				Messaging.Pool.__instance = Messaging.Pool()

			return Messaging.Pool.__instance

		def release(self):
			self.pool = None
			self.event.awake()

		def push(self, msg):
			try:
				self.pool.append(msg)

				# pop() returns pushed message
				self.event.awake()

			except Exception as e:
				self.logger.exception(e)

		def pop(self):
			# blocked if empty
			if self.pool is not None and len(self.pool) == 0:
				self.event.wait()

			if self.pool is None:
				raise Stop('message pool was released')

			return self.pool.pop()
	"""

	# inner-class
	class Server(BaseHTTPRequestHandler):
		@staticmethod
		def create(port, handler):
			host = ('0.0.0.0', port)
			def impl(*args):
				Messaging.Server(handler, *args)
			return HTTPServer(host, impl)

		def __init__(self, handler, *args):
			self.handler = handler

			# call super().__init__() after assign
			BaseHTTPRequestHandler.__init__(self, *args)

		def getContent(self):
			length = int(self.headers['Content-Length'])
			if length == 0:
				return None

			return self.rfile.read(length)

		def do_PUT(self):
			contents = self.getContent()
			thread = threading.Thread(target=self.handler, args=(contents,))
			thread.setDaemon(True)
			thread.start()
			self.send_response(200)

		def do_POST(self):
			contents = self.getContent()
			returned = self.handler(contents)
			message  = Json.dump(returned)

			self.send_response(200)
			self.send_header('Content-type', 'application/json')
			self.end_headers()
			self.wfile.write(message)

	# inner-class
	class Client:
		def __init__(self):
			self.logger = Logger.getInstance()

			self.http = None
			self.header = {
				'Content-Type': 'application/json'
			}

		def __del__(self):
			del self.http

		def request(self, method, url, headers={}, body=None, raiseIfNotOk=True):
			if TaskManager.getInstance().isStandalone:
				return

			mergedHeader = self.header
			mergedHeader.update(headers)

			if body is not None:
				body = Json.dump(body)

			# request
			self.logger.info('== REQUEST\n'
							 '{0} {1}\n'.format(method, url))

			failed = True
			while failed:
				try:
					self.http = httplib.HTTPConnection(Environment.ADDRESS, Environment.PORT)
					self.http.request(method, url, body, mergedHeader)

					failed = False

				except Exception as e:
					if self.http:
						del self.http

					self.logger.exception(e)
					time.sleep(1)

			# response
			response = self.http.getresponse()

			self.logger.info('== RESPONSE\n'
							 '{0} {1}\n'.format(response.status, response.reason))

			# check response
			if raiseIfNotOk and not (200 <= response.status < 300):
				raise Exception('{0} {1}'.format(response.status, response.reason))

			return response

class Json:
	@staticmethod
	def dump(dictData):
		return json.dumps(dictData, sort_keys=True, indent=2)

	@staticmethod
	def load(strData):
		return json.loads(strData)

class Stop(BaseException):
	def __init__(self, msg='STOP !'):
		self.msg = msg

	def __str__(self):
		return self.msg

class IVirtualization:
	class IHypervisor:
		def __init__(self):
			pass

		@property
		def source(self):
			pass

		def isGuest(self):
			pass

	class IPlatform:
		def __init__(self):
			pass

		@property
		def target(self):
			pass

		@property
		def mount(self):
			pass

class Virtualization:
	__instance = None

	def __init__(self):
		#  current machine != Environment server
		self.taskMgr  = TaskManager.getInstance()
		self.platform = self.taskMgr.properties.get('platform')

	@staticmethod
	def getInstance():
		if Virtualization.__instance is None:
			Virtualization.__instance = Virtualization()

		return Virtualization.__instance

	@property
	def done(self):
		if self.taskMgr.isStandalone:
			return False

		if self.platform is None:
			return False

		return Environment.HYPERVISOR.isGuest()

	@property
	def isRequired(self):
		if self.taskMgr.isStandalone:
			return False

		if self.platform is None:
			return False

		if not self.done:
			return True

	def attempt(self):
		Messaging.request(Messaging.Type.VIRTUALIZE)

	def mountSharedFolder(self):
		Virtualization.Guest.get().mount()

	def getMountPath(self):
		return Virtualization.Guest.get().target

	# inner-class
	class Hypervisor:
		class VMware(IVirtualization.IHypervisor):
			PRESET = {
				'win': r'\\vmware-host\Shared Folders',
				'linux': '/mnt/hgfs',
			}

			MAC_ADDRESS_PREFIX = '00:0c:'

			def __init__(self):
				IVirtualization.IHypervisor.__init__(self)

			@property
			def source(self):
				for key, value in Virtualization.Hypervisor.VMware.PRESET.iteritems():
					if Misc.isPlatform(key):
						return value

				raise Exception('undefined platform {0}'.format(sys.platform))

			def isGuest(self):
				prefix = Virtualization.Hypervisor.VMware.MAC_ADDRESS_PREFIX
				return any(mac for mac in Misc.getMACAddresses() if mac.startswith(prefix))

		class VirtualBox(IVirtualization.IHypervisor):
			MAC_ADDRESS_PREFIX = '08:00:'

			def __init__(self):
				IVirtualization.IHypervisor.__init__(self)

			@property
			def source(self):
				raise Exception('undefined platform {0}'.format(sys.platform))

			def isGuest(self):
				prefix = Virtualization.Hypervisor.VirtualBox.MAC_ADDRESS_PREFIX
				return any(mac for mac in Misc.getMACAddresses() if mac.startswith(prefix))

	# inner-class
	class Guest:
		@staticmethod
		def get():
			if Misc.isPlatform('win'):
				return Virtualization.Guest.Windows()

			elif Misc.isPlatform('linux'):
				return Virtualization.Guest.Linux()

			else:
				raise Exception('unsupported platform {0}'.format(sys.platform))

		class Windows(IVirtualization.IPlatform):
			def __init__(self):
				IVirtualization.IPlatform.__init__(self)

			@property
			def target(self):
				return 'z:\\'

			def mount(self):
				cmd = [
					'net',
					'use',
					self.target[:-1], # without back-slash
					Environment.HYPERVISOR.source,
					'/PERSISTENT:NO'
				]

				ret, _out, _err = Process().execute(cmd)
				if ret != 0:
					raise RuntimeError('cannot mount')

		class Linux(IVirtualization.IPlatform):
			def __init__(self):
				IVirtualization.IPlatform.__init__(self)

			@property
			def target(self):
				# access directly
				return Environment.HYPERVISOR.source

			def mount(self):
				# do not mount
				pass

class Backup:
	def __init__(self):
		taskMgr = TaskManager.getInstance()

		self.targets = taskMgr.properties.get('backup')

		self.event = WaitEvent()
		self.event.awake()

	def wait(self):
		self.event.wait()

	def request(self, path):
		obj = {
			'path': path
		}
		Messaging.request(Messaging.Type.BACK_UP, obj)

	def run(self):
		# ignore
		if not self.targets:
			return

		self.event.reset()

		for target in self.targets:
			path = os.path.abspath(target)

			if os.path.isfile(path):
				self.request(path)
			else:
				walk = path
				for root, _, files in os.walk(walk):
					for f in files:
						path = os.path.join(root, f)
						if os.path.isfile(path):
							self.request(path)

		self.event.awake()

class Misc:
	__ipaddr = None
	__macaddr = None

	@staticmethod
	def getAvailablePort():
		sock = socket.socket()
		try:
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			sock.bind(('', 0))

			return sock.getsockname()[1]
		finally:
			sock.close()

	@staticmethod
	def getLocalIPAddresses():
		"""
		socket.getaddrinfo() function returns a list of 5-tuples with the following structure:

			(family, socktype, proto, canonname, sockaddr)

		sockaddr is a tuple describing a socket address,
			whose format depends on the returned family
				(a (address, port                     ) 2-tuple for AF_INET,
				 a (address, port, flow info, scope id) 4-tuple for AF_INET6)
		"""

		addrinfo = socket.getaddrinfo(socket.gethostname(), 0, socket.AF_INET)
		ipaddr   = set(addr[4][0] for addr in addrinfo)

		# no-duplications
		return list(set(ipaddr))

	@staticmethod
	def isPlatform(platform):
		return sys.platform.startswith(platform)

	@staticmethod
	def isWindows():
		return Misc.isPlatform('win')

	@staticmethod
	def getIPAddressOfActivatedNIC():
		if Misc.__ipaddr is None:
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			try:
				sock.connect((Environment.ADDRESS, Environment.PORT))
				Misc.__ipaddr = sock.getsockname()[0] # host pair => (address, port)
			finally:
				sock.close()

		return Misc.__ipaddr

	@staticmethod
	def getMACAddresses():
		if Misc.__macaddr is None:
			macaddr = []
			proc = Process()

			regex = re.compile('([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})')

			if Misc.isWindows():
				out = proc.execute(['wmic', 'nic', 'get', 'macaddress', '/all'])[1]
				for line in out.splitlines():
					if not regex.match(line):
						continue

					macaddr.append(line.strip())

			else:
				out = proc.execute(['/sbin/ifconfig'])[1]
				for line in out.splitlines():
					if 'HWaddr' not in line:
						continue

					hwaddr = regex.search(line).group().strip()
					macaddr.append(hwaddr)

			for iter, mac in enumerate(macaddr):
				macaddr[iter] = mac.replace('-', ':').lower()

			Misc.__macaddr = macaddr

		return Misc.__macaddr

	@staticmethod
	def download(url, path, callback=None):
		url_lib = urllib2.urlopen(url)
		meta    = url_lib.info()
		size    = int(meta.getheaders('Content-Length')[0])

		BLOCK_SIZE = 8192
		written    = 0

		fp = open(path, 'wb')

		cb = None
		if isinstance(callback, Misc.ICallback):
			cb = callback(fp, url, size)

		try:
			if cb:
				cb.prepare()

			while written < size:
				content = url_lib.read(BLOCK_SIZE)
				written += len(content)
				fp.write(content)

			if cb:
				cb.succeed()

		except:
			if cb:
				cb.failed()

			if os.path.isfile(path):
				os.remove(path)

			raise

		finally:
			if fp:
				fp.close()

	class ICallback:
		def __init__(self, fp, path, size):
			self.fp = fp
			self.path = path
			self.size = size

		def prepare(self):
			pass

		def succeed(self):
			pass

		def failed(self):
			pass

class Process:
	# GPF: General Protection Fault
	@staticmethod
	def disableWindowsGPF():
		if not sys.platform.startswith('win'):
			return

		import ctypes

		"""
		SetErrorMode() function
		 - see https://msdn.microsoft.com/en-us/library/windows/desktop/ms680621(v=vs.85).aspx

		GetErrorMode() function
		 - supported from Windows Vista
		 - see https://msdn.microsoft.com/en-us/library/windows/desktop/ms679355(v=vs.85).aspx

		"""

#		SEM_FAILCRITICALERRORS     = 0x0001
#		SEM_NOALIGNMENTFAULTEXCEPT = 0x0004
		SEM_NOGPFAULTERRORBOX      = 0x0002
#		SEM_NOOPENFILEERRORBOX     = 0x8000

		isGPFEnabled = lambda flags: flags & SEM_NOGPFAULTERRORBOX == 0

		flags = ctypes.windll.kernel32.GetErrorMode()

		if not isGPFEnabled(flags):
			return

		ctypes.windll.kernel32.SetErrorMode(SEM_NOGPFAULTERRORBOX)

	@staticmethod
	def enableDump(procName, pid):
		if sys.platform.startswith('win'):
			from distutils.spawn import find_executable
			"""
			ProcDump from Windows Sysinternals
			 - https://technet.microsoft.com/en-us/sysinternals/dd996900.aspx
			"""
			procDump = find_executable('procdump')
			if procDump is None:
				raise Exception('procdump was not found')

			# procName is used as dump file name
			cmd= [procDump, '-e', '-ma', '-accepteula', '{0}'.format(pid), procName]
			subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stdout)

		else:
			import resource
			"""
			equivalent 'ulimit' command
			"""
			resource.setrlimit(resource.RLIMIT_CORE, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))

	def __init__(self):
		self.logger       = Logger.getInstance()
		self.process      = None
		self.cmd          = None
		self.isTerminated = False

		Process.disableWindowsGPF()

	def execute(self, cmd, dump=False, shell=False, wait=True):
		self.cmd = {k: v for k, v in locals().iteritems() if k != 'self'}
		self.logger.info('execute: {0}'.format(self.cmd))

		pipe = subprocess.PIPE

		self.process = subprocess.Popen(cmd, stdout=pipe, stderr=pipe, shell=shell)

		self.isTerminated = False

		if dump:
			Process.enableDump(cmd[0], self.process.pid)

		retval = None
		stdout = None
		stderr = None

		while wait and retval is None:
			retval = self.process.poll()

			if self.isTerminated:
				raise Stop()

			time.sleep(0.1)

		retval = self.process.poll()

		# done
		if retval is not None:
			stdout, stderr = self.process.communicate()

			self.process   = None
			self.cmd       = None

		return retval, stdout, stderr

	def terminate(self):
		if self.process is None:
			return

		self.isTerminated = True
		self.process.terminate()

class TaskHelper:
	def __init__(self):
		self.taskMgr   = TaskManager.getInstance()
		self.logger    = Logger.getInstance()
		self.processes = []

	def interface(self, **kwargs):
		callees = {
			'mail'   : self.sendMail,
			'process': self.executeProcess,
			'plugin' : self.getPlugin,
		}

		dups = set(kwargs.keys()) & set(callees.keys())
		for key in dups:
			return callees[key](kwargs)

	def sendMail(self, kwargs):
		mailForm = kwargs.get('mail', {})

		Messaging.request(Messaging.Type.SEND_MAIL, mailForm)

	def executeProcess(self, kwargs):
		cmd   = kwargs.get('process', []   )
		dump  = kwargs.get('dump'   , False)
		shell = kwargs.get('shell'  , False)
		wait  = kwargs.get('wait'   , True )

		proc = Process()

		if not wait:
			self.processes.append(proc)

		ret, out, err = proc.execute(cmd, dump=dump, shell=shell, wait=wait)

		return ret, out, err

	def terminateProcesses(self):
		for i, process in enumerate(self.processes):
			self.logger.info('terminating processes: [{0}/{1}] {2}'.format(i + 1, len(self.processes), process.cmd))
			process.terminate()

	def getPlugin(self, kwargs):
		plugin = kwargs.get('plugin', '')

		return TaskManager.Plugin(plugin).get()

def main():
	if len(sys.argv) < 2:
		print ('usage: python {0} <script> [<seq>] [<option> ...]\n'
			   '        script          task script path\n'
			   '        seq             seq. of task\n'
			   ''.format(sys.argv[0]))

		sys.exit(1)

	# default
	script = sys.argv[1]
	seq    = 'standalone'

	# seq.
	if len(sys.argv) > 2:
		seq = sys.argv[2]

	# more options
	opts = sys.argv[3:]

	# define
	Environment.HYPERVISOR = Virtualization.Hypervisor.VMware()

	# worker do task
	worker = Worker(script, seq)

	if '--check-property' in opts:
		worker.checkMissingProperties()
	else:
		worker.ready().do()

if __name__ == '__main__':
	main()

