# -*- coding: utf-8 -*-
import os

from vix import VixHost
from vix import VixVM

class PowerState:
	POWERING_OFF    = VixVM.VIX_POWERSTATE_POWERING_OFF
	POWERED_OFF     = VixVM.VIX_POWERSTATE_POWERED_OFF
	POWERING_ON     = VixVM.VIX_POWERSTATE_POWERING_ON
	POWERED_ON      = VixVM.VIX_POWERSTATE_POWERED_ON
	SUSPENDING      = VixVM.VIX_POWERSTATE_SUSPENDING
	SUSPENDED       = VixVM.VIX_POWERSTATE_SUSPENDED

class VirtualMachine:
	def __init__(self, config):
		self.config  = config
		self.vixHost = VixHost()
		self.vixVM   = self.vixHost.open_vm(self.config)

		self.sharedFolder = VirtualMachine.SharedFolder(self)

	def __del__(self):
		self.close()

	def close(self):
		del self.vixVM
		del self.vixHost

	# return self

	def on(self):
		if self.vixVM.is_running:
			return self

		self.vixVM.power_on(True)
		return self

	def off(self, fromGuest=True):
		if self.isIdle():
			return self

		self.vixVM.power_off(fromGuest)
		return self

	def suspend(self):
		if self.isIdle():
			return self

		self.vixVM.suspend()
		return self

	def clone(self, dst):
		self.vixVM.clone(dst)
		return self

	def wait(self, timeout=60):
		self.vixVM.wait_for_tools(timeout)
		return self

	def login(self, username, password, interactive=False):
		self.vixVM.login(username, password, interactive)
		return self

	def mkdir(self, path):
		if self.isdir(path):
			return self

		head, _tail = os.path.split(path)
		if not self.isdir(head):
			self.mkdir(head)

		self.vixVM.create_directory(path)
		return self

	def copyToGuest(self, src, dst):
		self.vixVM.copy_host_to_guest(src, dst)
		return self

	def copyFromGuest(self, src, dst):
		self.vixVM.copy_guest_to_host(src, dst)
		return self

	def remove(self, path):
		if self.isfile(path):
			self.vixVM.file_delete(path)
		else: # self.isdir(path):
			self.vixVM.dir_delete(path)
		return self

	def run(self, prog, args, wait=False):
		self.vixVM.proc_run(prog, args, wait)
		return self

	def script(self, interpreter, text, wait=False):
		self.vixVM.run_script(text, interpreter, wait)
		return self

	def snapshot(self, name, desc=''):
		self.vixVM.create_snapshot(name, desc)
		return self

	# return result

	def isOff(self):
		return self.vixVM.power_state in (PowerState.POWERING_OFF, PowerState.POWERED_OFF)

	def isSuspended(self):
		return self.vixVM.power_state in (PowerState.SUSPENDING, PowerState.SUSPENDED)

	def isIdle(self):
		return not self.vixVM.is_running

	def isfile(self, path):
		return self.vixVM.file_exists(path)

	def isdir(self, path):
		return self.vixVM.dir_exists(path)

	def getenv(self, var):
		return self.vixVM.var_read(var, VixVM.VIX_GUEST_ENVIRONMENT_VARIABLE)

	# inner-class
	class SharedFolder:
		def __init__(self, vm):
			self.vm = vm

		def enable(self):
			self.vm.vixVM.share_enable(True)

		def disable(self):
			self.vm.vixVM.share_enable(False)

		def __len__(self):
			return self.vm.vixVM.get_shared_folder_count()

		def get(self, index):
			return self.vm.vixVM.get_shared_folder_state(index)

		def set(self, name, path, writable=True):
			self.vm.vixVM.share_set_state(name, path, writable)

		def add(self, name, path, writable=True):
			self.vm.vixVM.add_shared_folder(name, path, writable)

		def remove(self, name):
			self.vm.vixVM.share_remove(name)

		def __iter__(self):
			for i in range(len(self)):
				yield self.get(i)

			raise StopIteration

