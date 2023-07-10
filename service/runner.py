# -*- coding: utf-8 -*-
import datetime
import hashlib
import httplib
import json
import multiprocessing
import os
import subprocess
import sys
import threading
import urllib.requst

from iservice import IService
from vmmgr import VirtualMachineManager
from task import state

def popen(executable):
	return subprocess.Popen(executable, shell=True, close_fds=True)

class Runner(IService):
	def __init__(self):
		IService.__init__(self)

		self.infoFile  = self.init.config['task']['info']
		self.workspace = os.path.abspath(self.init.config['task']['workspace'])
		self.plugin    = os.path.abspath(self.init.config['task']['plugin'])
		self.backupDir = self.init.config['virtualization']['backup']

		self.tasks = {}
		self.lock  = threading.Lock()
		self.vmmgr = VirtualMachineManager()

		if not os.path.isfile(self.infoFile) or os.stat(self.infoFile).st_size == 0:
			self.save()

		self.load()

	def load(self):
		with self.lock:
			self.tasks = self.util.jsonfile(self.infoFile).load()

	def save(self):
		with self.lock:
			self.util.jsonfile(self.infoFile).save(self.tasks)

	def getUtcTime(self):
		# 2016-05-06 07:38:26.779000
		# ~~~~~~~~~~~~~~~~~~~
		return str(datetime.datetime.utcnow())[:19]

	def generateSeq(self):
		hash = hashlib.md5(self.getUtcTime()).hexdigest()
		return hash[:8]

	def getUpdatedTime(self):
		return os.path.getmtime(self.infoFile)

	def exists(self, taskName, seq=None):
		if taskName in self.tasks:
			if seq is None:
				return True

			elif seq in self.tasks[taskName]:
				return True

		return False

	def checkRegistered(self, taskName, seq):
		if not self.exists(taskName, seq):
			raise KeyError('task [{0}@{1}] was not registered'.format(taskName, seq))

	def getTaskDirectory(self, taskName):
		return os.path.join(self.workspace, taskName)

	def getTaskScript(self, taskName):
		return os.path.join(self.getTaskDirectory(taskName), '{0}.py'.format(taskName))

	def getPluginDirectory(self):
		return self.plugin

	def getPluginScript(self, pluginName):
		return os.path.join(self.getPluginDirectory(), '{0}.py'.format(pluginName))

	def register(self, taskName):
		task = self.getTaskScript(taskName)
		if not os.path.isfile(task):
			raise RuntimeError('register: [{0}] task script was not found'.format(taskName))

		"""
		# for multiple task, remove this and more consider seq.
		if self.exists(taskName):
			raise ValueError('task [{0}] is already registered'.format(taskName))
		"""

		if not self.exists(taskName):
			self.tasks[taskName] = {}

		seq = self.generateSeq()
		self.tasks[taskName][seq] = {}

		attr = {
			'reg-time': self.getUtcTime()
		}
		self.resetAttributes(taskName, seq, attr)

		self.logger.debug('registered: {0}@{1}'.format(taskName, seq))

		return seq

	def remove(self, taskName, seq):
		self.checkRegistered(taskName, seq)
		self.logger.debug('remove: {0}@{1}'.format(taskName, seq))

		statement = self.get(taskName, seq, 'state')
		if state.isInProgress(statement):
			try:
				self.stop(taskName, seq)
			except:
				pass

		self.tasks[taskName].pop(seq)

		if len(self.tasks[taskName]) == 0:
			self.tasks.pop(taskName)

		self.save()

	def get(self, taskName, seq=None, key=None):
		self.checkRegistered(taskName, seq)

		task = self.tasks[taskName]
		if seq is None:
			return task

		else:
			task = task[seq]

			if key is None:
				return task

			elif key in task:
				return task[key]

		return None

	def set(self, taskName, seq, key, value):
		self.checkRegistered(taskName, seq)
		self.logger.debug('set: {0}@{1}[{2}] = {3}'.format(taskName, seq, key, value))

		with self.lock:
			self.tasks[taskName][seq][key] = value

	def setAttributes(self, taskName, seq, obj):
		for key, value in obj.iteritems():
			if key == 'state':
				self.set(taskName, seq, 'state-name', state.asString(value))

				if value == state.RUNNING:
					self.set(taskName, seq, 'exec-time', self.getUtcTime())

			self.set(taskName, seq, key, value)

		self.save()

	def resetAttributes(self, taskName, seq, attr={}):
		obj = {
			'state': state.NONE,
		}
		obj.update(attr)
		self.setAttributes(taskName, seq, obj)

	def getAllTaskInfo(self, includeHiddenTasks=False):
		tasks = {}
		for taskName, infos in self.tasks.iteritems():
			tasks[taskName] = {}

			for seq, info in infos.iteritems():
				if not includeHiddenTasks and info.get('hidden', False) is True:
					del tasks[taskName]
					continue

				tasks[taskName][seq] = info

		return tasks

	def isTaskInProgress(self, taskName, seq):
		return self.get(taskName, seq, 'state') == state.RUNNING

	def pushMessage(self, taskName, seq, messageType, value):
		# <type> parameter
		#  - 'control': control message. handling in worker
		#  - 'user': user-defined message. handling in handler() function in task

		self.checkRegistered(taskName, seq)

		header = {
			'Content-Type': 'application/json'
		}

		address = self.get(taskName, seq, 'address')
		port    = self.get(taskName, seq, 'port')
		host    = '{0}:{1}'.format(address, port)

		obj = {
			'type': messageType,
			'value': value
		}
		msg = json.dumps(obj, sort_keys=True, indent=2)

		self.logger.debug('push: http://{0}/ <= {1}'.format(host, msg))

		try:
			http = httplib.HTTPConnection(host)
			http.request('PUT', '/', msg, header)
			http.getresponse()

		except IOError as e:
			# socket.error is now a child class of IOError
			# disconnected ?
			obj = {
				'state': state.DISCONNECTED,
				'err': 'disconnected ? (errno: {0})'.format(e.errno)
			}
			self.setAttributes(taskName, seq, obj)

			raise

	def callWorker(self, taskName, seq, params=[]):
		statement = self.get(taskName, seq, 'state')
		if statement & state.FLAG_IN_PROGRESS != 0:
			raise DeprecationWarning('{0}@{1} is in progress ({2})'.format(taskName, seq, state.asString(statement)))

		self.setAttributes(taskName, seq, {'state': state.INITIATING})

		worker = os.path.join(os.path.abspath('task'), 'worker.py')
		task   = self.getTaskScript(taskName)

		executable = [sys.executable, worker, task, str(seq)]

		if params:
			executable.extend(params)

		self.logger.debug('execute: {0}'.format(str(executable)))

		mp = multiprocessing.Process(target=popen, args=(executable,))
		mp.daemon = True
		mp.start()

	def checkProperty(self, taskName, seq):
		self.logger.debug('check-property: {0}@{1}'.format(taskName, seq))

		self.callWorker(taskName, seq, ['--check-property'])

	def run(self, taskName, seq):
		self.logger.debug('run: {0}@{1}'.format(taskName, seq))

		self.callWorker(taskName, seq)

	def stop(self, taskName, seq):
		self.logger.debug('stop: {0}@{1}'.format(taskName, seq))
		obj = {
			'state': state.STOP
		}
		self.pushMessage(taskName, seq, 'control', obj)

	def runTaskInVM(self, taskName, seq):
		self.vmmgr.check()

		vm = None

		try:
			platform = self.get(taskName, seq, 'platform')

			# open and on
			vm = self.vmmgr.openIdleVM(platform)
			self.vmmgr.on(vm)

			self.set(taskName, seq, 'vm-config', vm.config)

			# prepare
			self.vmmgr.prepareVM(vm)

			# run
			self.vmmgr.runTask(vm, taskName, seq)

		except Exception as e:
			self.logger.error(e)
			self.vmmgr.off(vm)
			raise

		finally:
			if vm:
				# succeed to open => task info was changed
				vm.close()

	def stopVM(self, taskName, seq):
		self.vmmgr.check()

		vm = None

		try:
			platform = self.get(taskName, seq, 'platform')
			vmcfg    = self.get(taskName, seq, 'vm-config')

			vm = self.vmmgr.open(vmcfg, platform)
			self.vmmgr.off(vm)

		except Exception as e:
			self.logger.error(e)
			raise

		finally:
			if vm:
				vm.close()

	def backupFromVM(self, taskName, seq, path):
		"""
		# legacy with vixpy

		self.vmmgr.check()

		vm = None

		try:
			platform = self.get(taskName, seq, 'platform')
			vmcfg    = self.get(taskName, seq, 'vm-config')

			vm = self.vmmgr.open(vmcfg, platform)
			self.vmmgr.prepareVM(vm)

			self.vmmgr.copyTaskFromVM(vm, taskName, seq, path)

		except Exception as e:
			self.logger.error(e)
			raise

		finally:
			if vm:
				vm.close()
		"""
		# <type> parameter
		#  - 'http://<worker address>/backup/<path/to/want>': control message. handling in worker

		self.checkRegistered(taskName, seq)

		address = self.get(taskName, seq, 'address')
		port    = self.get(taskName, seq, 'port')
		url     = 'http://{0}:{1}/{2}'.format(address, port, path)

		self.logger.debug('backup: download from {0}'.format(url))

		try:
			backupDir = os.path.join(self.workspace, taskName, self.backupDir)
			if not os.path.isdir(backupDir):
				os.makedirs(backupDir)

			filename = os.path.basename(path)
			local = os.path.join(backupDir, filename)

			urllib.requst.urlretrieve(url, local)

		except Exception as e:
			# socket.error is now a child class of IOError
			# disconnected ?
			obj = {
				'state': state.DISCONNECTED,
				'err': 'disconnected ? (errno: {0})'.format(e.errno)
			}
			self.setAttributes(taskName, seq, obj)

			raise

	def autorun(self):
		for taskName, infos in self.tasks.iteritems():
			for seq, info in infos.iteritems():
				if info.get('autorun', False) is True:
					try:
						self.logger.info('autorun: {0}@{1} try to run'.format(taskName, seq))
						self.run(taskName, seq)
					except DeprecationWarning as _e:
						self.logger.debug('autorun: {0}@{1} already running'.format(taskName, seq))
						# do nothing
						pass

	def checkAlive(self):
		dummyObj = {}

		for taskName, infos in self.tasks.iteritems():
			for seq, _info in infos.iteritems():
				statement = self.get(taskName, seq, 'state')

				if not state.isInProgress(statement):
					continue

				try:
					self.logger.info('check-alive: checking {0}@{1}'.format(taskName, seq))
					self.pushMessage(taskName, seq, 'control', dummyObj)
				except:
					self.logger.warning('check-alive: {0}@{1} no response'.format(taskName, seq))
					# do nothing
					# set 'DISCONNECTED' state in pushMessage() method
					pass

