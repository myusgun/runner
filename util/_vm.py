# -*- coding: utf-8 -*-
import os

from vmware_vmrun import VMRun
from vmware_vixpy import VixHost

class VirtualMachine:
	def __init__(self, config):
		self.config  = config
		self.vixHost = VixHost()
		self.vixVM   = self.vixHost.open(self.config)
		self.vmrun   = VMRun(self.config)

		self.sharedFolder = VirtualMachine.SharedFolder(self)

	def __del__(self):
		self.close()

	@staticmethod
	def setCommandLineTool(path):
		VMRun.setExecutable(path)

	def close(self):
		del self.vixVM
		del self.vixHost

	# return self

	def on(self):
		if self.vixVM.power_state in ('Powering On', 'Powered On'):
			return self

		self.vixVM.on(True)
		return self

	def off(self, fromGuest=True):
		if self.isIdle():
			return self

		self.vixVM.off(from_guest=fromGuest)
		return self

	def suspend(self):
		if self.isIdle():
			return self

		self.vixVM.suspend()
		return self

	def clone(self, dst):
		self.vmrun.clone(dst)
		return self

	def wait(self):
		self.vixVM.wait()
		return self

	def login(self, username, password):
		self.username = username
		self.password = password
		self.vixVM.login(username, password)
		return self

	def mkdir(self, path):
		if self.isDirectory(path):
			return self

		head, tail = os.path.split(path)
		if not self.isDirectory(head):
			self.mkdir(head)

		self.vixVM.mkdir(path)
		return self

	def copyToGuest(self, src, dst):
		self.vixVM.copy_to(src, dst)
		return self

	def copyFromGuest(self, src, dst):
		self.vixVM.copy_from(src, dst)
		return self

	def remove(self, path):
		self.vixVM.rm(path)
		return self

	def run(self, prog, args, wait=False):
		self.vixVM.run(prog, args, wait, window=True)
		return self

	def script(self, interpreter, text, wait=False):
		self.vixVM.eval(interpreter, text, wait)
		return self

	def snapshot(self, name, desc=''):
		self.vixVM.snapshot(name, desc)
		return self

	# return result

	def isOff(self):
		return self.vixVM.power_state in ('Powering Off', 'Powered Off')

	def isSuspended(self):
		return self.vixVM.power_state in ('Suspending', 'Suspended')

	def isIdle(self):
		return self.isOff() or self.isSuspended()

	def isfile(self, path):
		return self.vixVM.exists(path)

	def isDirectory(self, path):
		return self.vixVM.exists_dir(path)

	def getenv(self, var):
		return self.vixVM.read_env_var(var)

	# inner-class
	class SharedFolder:
		def __init__(self, vm):
			self.vm = vm

		def enable(self):
			self.vm.vixVM.enable_sharedfolders()

		def disable(self):
			self.vm.vixVM.disable_sharedfolders()

		def __len__(self):
			return self.vm.vixVM.num_sharedfolders()

		def get(self, index):
			return self.vm.vixVM.get_sharedfolder(index)

		def set(self, name, path, writable=True):
			self.vm.vixVM.set_sharedfolder(name, path, writeable=writable)

		def add(self, name, path, writable=True):
			self.vm.vixVM.add_sharedfolder(name, path, writeable=writable)

		def remove(self, name):
			self.vm.vixVM.del_sharedfolder(name)

		def __iter__(self):
			for i in range(len(self)):
				yield self.get(i)

			raise StopIteration

