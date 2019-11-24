# -*- coding: utf-8 -*-
import importlib
import os
import sys

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
			return None

		depth -= 1

	for e in os.listdir(path):
		fullpath = os.path.join(path, e)

		if os.path.isdir(fullpath):
			entries = traverse(fullpath, depth)
			if entries:
				dirs.update({e: entries})

		elif os.path.isfile(fullpath):
			files.append(e)

	return {'dir': dirs, 'file': files}

def zipDir(zipName, dirpath):
	import zipstream
	from flask import Response

	z = zipstream.ZipFile(compression=zipstream.ZIP_DEFLATED)
	for root, dirs, files in os.walk(dirpath):
		for entry in dirs:
			abspath = os.path.join(root, entry)
			arcpath = abspath.replace(dirpath, '')
			z.write(abspath, arcpath)
		for entry in files:
			abspath = os.path.join(root, entry)
			arcpath = abspath.replace(dirpath, '')
			z.write(abspath, arcpath)

	resp = Response(z, mimetype='application/zip')
	resp.headers['Content-Disposition'] = 'attachment; filename={0}'.format(zipName)

	return resp
