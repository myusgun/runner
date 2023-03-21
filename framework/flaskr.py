# -*- coding: utf-8 -*-
import logging

from flask import Flask
from flask import redirect
from flask import request
from flask import Response
from flask import send_file
from flask.templating import render_template

class FlaskR(Flask):
	class LogLevel:
		CRITICAL = 50
		FATAL = CRITICAL
		ERROR = 40
		WARNING = 30
		WARN = WARNING
		INFO = 20
		DEBUG = 10
		NOTSET = 0

	def __init__(self, *args, **kwargs):
		Flask.__init__(self, *args, **kwargs)

		self.debug = True

		self.host = None
		self.port = None

		# method
		self.start = None

	def setLogLevel(self, level):
		logging.getLogger('werkzeug').setLevel(level)

	def bind(self, host, port):
		self.host = host
		self.port = port

		return self

	def simple_start(self):
		self.run(host=self.host,
				 port=self.port,
				 use_reloader=False, # for multi threading (i.e., scheduler)
				)

	@property
	def simple(self):
		self.start = self.simple_start

		self.setLogLevel(FlaskR.LogLevel.ERROR)

		return self

	@property
	def gevent(self):
		from gevent.pywsgi import WSGIServer

		self.server = WSGIServer((self.host, self.port), self, log=None)
		self.start = self.server.serve_forever

		import signal

		def interrupt(signum, frame):
			self.server.stop()

		signal.signal(signal.SIGINT, interrupt)

		return self

	@property
	def request(self):
		return request

	@property
	def session(self):
		return session

	def render(self, template_name_or_list, **context):
		return render_template(template_name_or_list, **context)

	def redirect(self, url):
		return redirect(url)

	def sendFile(self, path, as_attachment=True):
		return send_file(path, as_attachment=as_attachment)

	def __addZipEntries(self, zipinstance, dirpath):
		for root, dirs, files in os.walk(dirpath):
			for entry in dirs:
				abspath = os.path.join(root, entry)
				arcpath = abspath.replace(dirpath, '')
				zipinstance.write(abspath, arcpath)
			for entry in files:
				abspath = os.path.join(root, entry)
				arcpath = abspath.replace(dirpath, '')
				zipinstance.write(abspath, arcpath)

	def createZipStream(self, dirpath):
		import zipstream

		zs = zipstream.ZipFile(compression=zipstream.ZIP_DEFLATED)

		self.__addZipEntries(zs, dirpath)

		return zs

	def zipStream(self, zips, zipName):
		resp = Response(zips, mimetype='application/zip')
		resp.headers['Content-Disposition'] = 'attachment; filename={0}'.format(zipName)

		return resp

