# -*- coding: utf-8 -*-
import importlib
import os
import sys

def getLocalIP():
	import socket
	return socket.gethostbyname(socket.getfqdn())

def readScript(path):
	with open(path, 'rb') as f:
		return f.read().decode('utf-8')

def getExamples():
	ret = {
		'task'  : readScript('example/task_example.py'  ),
		'plugin': readScript('example/plugin_example.py'),
	}

	return ret

def getPlugins(runner):
	path = runner.getPluginDirectory()
	if path not in sys.path:
		sys.path.append(path)

	splitted = map(os.path.splitext, os.listdir(path))
	modules  = [e[0] for e in splitted if e[1] == '.py']
	imports  = map(importlib.import_module, modules)
	plugins  = [getattr(module, 'Plugin') for module in imports]

	ret = {
		'plugins': modules,
		'args'   : {module: getattr(plugin, 'args' ) for module, plugin in zip(modules, plugins)},
		'types'  : {module: getattr(plugin, 'types') for module, plugin in zip(modules, plugins)},
	}

	# delete imported modules
	for module in imports:
		del module

	for module in modules:
		del sys.modules[module]

	return ret

def traverse(path, depth=None):
	dirs  = {}
	files = []

	if isinstance(depth, int):
		if depth == 0:
			return {}

		depth -= 1

	for e in os.listdir(path):
		fullpath = os.path.join(path, e)

		if os.path.isdir(fullpath):
			dirs.update({e: traverse(fullpath, depth)})

		elif os.path.isfile(fullpath):
			files.append(e)

	return {'dir': dirs, 'file': files}

