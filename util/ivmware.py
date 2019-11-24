# -*- coding: utf-8 -*-

class VirtualMachine:
	def __init__(self, config):
		self.config  = config
		raise NotImplementedError

	def __del__(self):
		self.close()

	def close(self):
		pass

	# return self

	def on(self):
		return self

	def off(self, fromGuest=True):
		return self

	def suspend(self):
		return self

	def clone(self, dst):
		return self

	def wait(self, timeout=60):
		return self

	def login(self, username, password, interactive=False):
		return self

	def mkdir(self, path):
		return self

	def copyToGuest(self, src, dst):
		return self

	def copyFromGuest(self, src, dst):
		return self

	def remove(self, path):
		return self

	def run(self, prog, args, wait=False):
		return self

	def script(self, interpreter, text, wait=False):
		return self

	def snapshot(self, name, desc=''):
		return self

	# return result

	def isOff(self):
		raise NotImplementedError

	def isSuspended(self):
		raise NotImplementedError

	def isIdle(self):
		raise NotImplementedError

	def isfile(self, path):
		raise NotImplementedError

	def isdir(self, path):
		raise NotImplementedError

	def getenv(self, var):
		raise NotImplementedError

