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
		raise NotImplementedError
		return self

	def off(self, fromGuest=True):
		raise NotImplementedError
		return self

	def suspend(self):
		raise NotImplementedError
		return self

	def clone(self, dst):
		raise NotImplementedError
		return self

	def wait(self, timeout=60):
		raise NotImplementedError
		return self

	def login(self, username, password, interactive=False):
		raise NotImplementedError
		return self

	def mkdir(self, path):
		raise NotImplementedError
		return self

	def copyToGuest(self, src, dst):
		raise NotImplementedError
		return self

	def copyFromGuest(self, src, dst):
		raise NotImplementedError
		return self

	def remove(self, path):
		raise NotImplementedError
		return self

	def run(self, prog, args, wait=False):
		raise NotImplementedError
		return self

	def script(self, interpreter, text, wait=False):
		raise NotImplementedError
		return self

	def snapshot(self, name, desc=''):
		raise NotImplementedError
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

