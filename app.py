# -*- coding: utf-8 -*-
import os
import shutil
import threading
import time

from collections import namedtuple

from framework import FlaskR
from service import Initializer
from service import Runner
from service import Mailer
from service import Statistics

import features

# create flask instance
app = FlaskR(__name__, static_folder='templates')

"""
-------------------------------------------------------------------------------------------------------------
| OBJ.          | RETURN TYPE | RETURN         | METHOD | URL                                 | BODY PARAM  |
=============================================================================================================
| get all tasks |        json |      all tasks | GET    | /api?tasks                          |             |
| - statistics  |        json |     statistics | GET    | /api?statistics                     |             |
| - check alive |        json |    check-alive | GET    | /api?check-alive                    |             |
| get mtime     |        json |     task mtime | GET    | /api?mtime                          |             |
| mail          |             |                | POST   | /api?mail                           | <mail form> |
| shutdown      |             |                | (ANY)  | /api?shutdown                       |             |
-------------------------------------------------------------------------------------------------------------
| register      |        text |           seq. | PUT    | /api/<task>                         |             |
| get           |        json | tasks all seq. | GET    | /api/<task>                         |             |
-------------------------------------------------------------------------------------------------------------
| get task info |        json | a task by seq. | GET    | /api/<task>/<seq>                   |             |
| remove        |             |                | DELETE | /api/<task>/<seq>                   |             |
| set attr      |             |                | POST   | /api/<task>/<seq>                   | <attrs>     |
-------------------------------------------------------------------------------------------------------------
| run           |             |                | POST   | /api/<task>/<seq>/run               |             |
| run           |             |                | POST   | /api/<task>/<seq>/run?virtualize    |             |
| stop          |             |                | POST   | /api/<task>/<seq>/stop              |             |
| push          |             |                | POST   | /api/<task>/<seq>/push?control      | <msg>       |
| push          |             |                | POST   | /api/<task>/<seq>/push?user         | <msg>       |
| reset         |             |                | POST   | /api/<task>/<seq>/reset             |             |
| backup        |             |                | POST   | /api/<task>/<seq>/backup?from=vm    | <vm-paths>  |
-------------------------------------------------------------------------------------------------------------
| DL plugin     |        file |  plugin script | GET    | /api/plugin/<name>                  |             |
-------------------------------------------------------------------------------------------------------------
| get task file |        json | dict(dir,file) | GET    | /api/file/<task>                    |             |
| DL task file  |        file |         a file | GET    | /api/file/<task>?path=<subpath>     |             |
| upload        |             |                | POST   | /api/file/<task>?subdir=<subdir>    | <multipart> |
| delete        |             |                | DELETE | /api/file/<task>                    |             |
-------------------------------------------------------------------------------------------------------------
| SERVICE TASK  |           * |              * | *      | /svc?*                              |             |
-------------------------------------------------------------------------------------------------------------

"""

# --------------------------------------------------------------
# Web UI, 메뉴 추가는 여기에
# --------------------------------------------------------------
PAGE_TUPLE = namedtuple('page_tuple', 'name, html, icon')
ARGS_TUPLE = namedtuple('args_tuple', 'name, pages, param')

PAGE = lambda name, html, icon: PAGE_TUPLE(name, html, icon)
PAGES = [
#        name                  web page file name       awesome font
#	PAGE(u'Home'             , 'home'                 , 'home'          ),
	PAGE(u'Tasks'            , 'tasks'                , 'tasks'         ),
	PAGE(u'How To'           , 'how_to'               , 'question'      )
]

# set template page
@app.route('/')
def root():
	return app.redirect('/tasks')

@app.route('/<any({0}):url>'.format(', '.join(page.html for page in PAGES)))
def renderPage(url):
	param = None
	if url == 'how_to':
		param = features.getExamples()

	name  = next(page.name for page in PAGES if page.html == url)
	args  = ARGS_TUPLE(name, PAGES, param)

	return app.render('{0}.html'.format(url), args=args)

# --------------------------------------------------------------
# ! IMPORTANT
# REST api
# --------------------------------------------------------------
init       = Initializer()
runner     = Runner()
mailer     = Mailer()
statistics = Statistics()

def toJson(obj):
	import json
	return json.dumps(obj, indent=2, sort_keys=2)

@app.route('/api', methods=['GET', 'POST'])
def api():
	try:
		method = app.request.method
		args   = app.request.args

		if 'shutdown' in args:
			app.request.environ.get('werkzeug.server.shutdown')()
			return ''

		if method == 'GET':
			if 'tasks' in args:
				showHidden = args.get('hidden', False)
				runner.load()
				obj = runner.getAllTaskInfo(includeHiddenTasks=showHidden)
				return toJson(obj)

			elif 'mtime' in args:
				mtime = runner.getUpdatedTime()
				return str(mtime)

			elif 'statistics' in args:
				statistics.load()
				obj = statistics.get()
				return toJson(obj)

			elif 'check-alive' in args:
				runner.checkAlive()
				return ''

		elif method == 'POST':
			if 'mail' in args:
				obj = app.request.get_json()
				init.logger.debug(obj)

				mailer.send(obj)
				return ''

		return '', 403

	except DeprecationWarning as e:
		init.logger.warn(str(e))
		return str(e), 304

	except Exception as e:
		init.logger.exception(e)
		return str(e), 500

@app.route('/api/<taskName>', methods=['GET', 'PUT'])
def apiTask(taskName):
	try:
		method = app.request.method

		if method == 'GET':
			obj = runner.get(taskName)
			return toJson(obj)

		elif method == 'PUT':
			seq = runner.register(taskName)
			runner.checkProperty(taskName, seq)

			obj = {
				'seq': seq
			}
			return toJson(obj)

	except KeyError as e:
		init.logger.warn(str(e))
		return str(e), 404

	except ValueError as e:
		init.logger.warn(str(e))
		return str(e), 409

	except Exception as e:
		init.logger.exception(e)
		return str(e), 500

@app.route('/api/<taskName>/<seq>', methods=['GET', 'DELETE', 'POST'])
def apiTaskSeq(taskName, seq):
	try:
		method = app.request.method

		if method == 'GET':
			obj = runner.get(taskName, seq)
			init.logger.debug(obj)

			return toJson(obj)

		elif method == 'DELETE':
			runner.remove(taskName, seq)
			return ''

		elif method == 'POST':
			obj = app.request.get_json()
			init.logger.debug(obj)

			runner.setAttributes(taskName, seq, obj)

			if 'state' in obj:
				hidden = runner.get(taskName, seq, key='hidden')
				if not hidden:
					statistics.set(taskName, seq, obj['state'])

			return ''

	except KeyError as e:
		init.logger.warn(str(e))
		return str(e), 404

	except Exception as e:
		init.logger.exception(e)
		return str(e), 500

@app.route('/api/<taskName>/<seq>/<cmd>', methods=['POST'])
def apiTaskSeqCmd(taskName, seq, cmd):
	try:
		if cmd == 'run':
			isRealMachine = 'virtualize' not in app.request.args

			if isRealMachine:
				runner.run(taskName, seq)
				return ''

			else:
				runner.runTaskInVM(taskName, seq)
				return ''

		elif cmd == 'stop':
			runner.stop(taskName, seq)
			return ''

		elif cmd == 'push':
			# critical item
			pushType = app.request.args.get('type')

			obj = app.request.get_json()
			init.logger.debug(obj)

			runner.pushMessage(taskName, seq, pushType, obj)
			return ''

		elif cmd == 'reset':
			runner.resetAttributes(taskName, seq)
			return ''

		elif cmd == 'backup':
			src = app.request.args.get('from', '')

			if src == 'vm':
				obj = app.request.get_json()
				init.logger.debug(obj)

				path = obj['path']

				runner.backupFromVM(taskName, seq, path)
				return ''

		return '', 403

	except DeprecationWarning as e:
		init.logger.warn(str(e))
		return str(e), 304

	except KeyError as e:
		init.logger.warn(str(e))
		return str(e), 404

	except IOError as e:
		init.logger.exception(e)
		return str(e), 599

	except Exception as e:
		init.logger.exception(e)
		return str(e), 500

@app.route('/api/plugin/<pluginName>', methods=['GET'])
def apiPlugin(pluginName):
	try:
		path = runner.getPluginScript(pluginName)
		if not os.path.isfile(path):
			return 'plugin not found', 404

		return app.sendFile(path)

	except IOError as e:
		init.logger.exception(e)
		return str(e), 599

	except Exception as e:
		init.logger.exception(e)
		return str(e), 500

# for client API
@app.route('/api/file/<taskName>', methods=['GET', 'POST', 'DELETE'])
def apiFile(taskName):
	try:
		method = app.request.method

		if method == 'GET':
			path = app.request.args.get('path')

			if not path:
				path = runner.getTaskDirectory(taskName)
				obj = features.traverse(path)

				return toJson(obj)

			else:
				path = os.path.join(runner.getTaskDirectory(taskName), path)
				if not os.path.isfile(path):
					return 'file not found', 404

				return app.sendFile(path)

		elif method == 'POST':
			f = app.request.files['file']
			if not f:
				return 'no file', 405

			name   = f.filename
			subdir = app.request.args['subdir'].lstrip('\\/')

			dirPath = os.path.join(runner.getTaskDirectory(taskName), subdir)
			if not os.path.isdir(dirPath):
				os.makedirs(dirPath)

			filePath = os.path.join(dirPath, name)
			f.save(filePath)

			return ''

		elif method == 'DELETE':
			path = runner.getTaskDirectory(taskName)
			for _retry in range(5):
				if not os.path.isdir(path):
					break

				try:
					shutil.rmtree(path)
				except:
					time.sleep(0.1)

			else:
				raise IOError('delete: [{0}] cannot delete'.format(path))

			return ''

	except Exception as e:
		init.logger.exception(e)
		return str(e), 500

class Lazy:
	def __init__(self, delay=3):
		self.event = threading.Event()
		self.delay = delay

	def autorun(self):
		init.logger.info('lazy-autorun: waiting {0} seconds ...'.format(self.delay))

		stopped = self.event.wait(self.delay)
		if stopped:
			init.logger.info('lazy-autorun: stopped')
			return

		init.logger.info('lazy-autorun: checking tasks ...')
		runner.checkAlive()
		threading.Thread(target=self.checkAlive).start()

		init.logger.info('lazy-autorun: executing autorun tasks ...')
		runner.autorun()

	def checkAlive(self):
		while not self.event.isSet():
			runner.checkAlive()
			time.sleep(1)

	def start(self):
		threading.Thread(target=self.autorun).start()

	def stop(self):
		self.event.set()

def main():
	port = init.config['port']
	lazy = Lazy()

	lazy.start()
	app.bind('0.0.0.0', port).gevent.start()
	lazy.stop()

if __name__ == '__main__':
	main()
