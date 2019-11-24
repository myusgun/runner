# -*- coding: utf-8 -*-
from util import Util

class TEST:
	__cnt = 0

	def __init__(self, func, *args):
		try:
			print '[TEST:{0}] {1}'.format(TEST.__cnt, func.__name__)
			func(*args)
			print '-- SUCCESS --'
		except Exception as e:
			print '-- FAILURE --'
			Util().logger.exception(e)
			print '------------'

		TEST.__cnt += 1

def vm_pysphere():
	import ssl
	import sys
	import time

	from pysphere import VIServer, VMPowerState

	try:
		def call(f, *args, **kwargs):
			fn = f.__name__ + '()'
			print '%-20s : ' % (fn),
			print f(*args, **kwargs)

		def callpretty(f, *args, **kwargs):
			fn = f.__name__ + '()'
			print '%-20s : ' % (fn)
			import pprint
			pprint.pprint(f(*args, **kwargs))
		# --------------------------------------------------------------
		ssl_default_ctx = ssl._create_default_https_context
		ssl._create_default_https_context = ssl._create_unverified_context
		# --------------------------------------------------------------
		server = VIServer()
		server.connect('localhost:443', 'cheese', '12qw!@QW', trace_file='pysphere.log')
		# --------------------------------------------------------------
		call(server.get_server_type)
		call(server.get_api_version)
		call(server.get_registered_vms)
		# --------------------------------------------------------------
		vm = server.get_vm_by_name('Clone of chu-15.04')
		# --------------------------------------------------------------
		call(vm.get_status)
		# --------------------------------------------------------------

		# off
		if vm.is_powered_on() and False:
			print 'shutting ',
			while vm.get_status() != VMPowerState.POWERED_OFF:
				try:
					vm.shutdown_guest()
				except:
					time.sleep(1)
				sys.stdout.write('.')
			print ' down'

		# on
		if vm.is_powered_off():
			vm.power_on()

		# boot up
		print 'booting ',
		while True:
			if vm.get_property('net', False) is not None:
				break

			time.sleep(1)
			sys.stdout.write('.')
		print ' up'

		# vmtools
		call(vm.get_tools_status)

		# login
		#vm.login_in_guest('cheese', '.')
		vm.list_processes()

		# --------------------------------------------------------------
	finally:
		# --------------------------------------------------------------
		server.disconnect()
		# --------------------------------------------------------------
		ssl._create_default_https_context = ssl_default_ctx
		# --------------------------------------------------------------

def vm_vixpy():
	import time
	from vixpy import VixHost

	vmx = {
		'ubuntu': r'E:\VMs\chu-14.04.4\chu-14.04.4.vmx',
		'win7': r'C:\Users\myusg\Desktop\vm\win7x64-cl1\win7x64-cl1.vmx'
	}

	target = 'win7'

	print vmx[target]

	host = VixHost()
	vm   = host.open(vmx[target])

	def power():
		if vm.power_state == '!Powered On':
			try:
				vm.off(from_guest=True)
			except:
				# ignore
				pass

		vm.on()

	def login():
		if target == 'win7':
			vm.login('qwer', 'qwer')
		elif target == 'ubuntu':
			vm.login('cheese', '.')

	def check():
		src = r'd:\asdf'
		dst = r'c:\asdf'

#		print vm.run('c:\\python27\\python.exe', '-c "import sys; print sys.platform')
		print vm.read_env_var('Path')
		print vm.read_env_var('OS')
		print vm.read_env_var('PATH')
		print vm.read_env_var('HOME')
		print vm.read_env_var('HOMEDRIVE')

		prog = 'C:\\Python27\\\\python.exe'
		args = 'C:\\_workspace\\test_print\\worker.py C:\\_workspace\\test_print\\test_print.py'
#		print vm.run(prog, args, False)

	def snapshot():
		vm.snapshot('1', '2')

	def shared():
		shared_root = r'\\vmware-host\Shared Folders'
		try:
			vm.add_sharedfolder('test', r'd:\asdf')
			vm.enable_sharedfolders()
		except:
			pass
		vm.run(r'c:\windows\explorer.exe', shared_root + r'\test', window=True)

#	TEST(power)
#	TEST(login)
#	TEST(check)
#	TEST(shared)
	TEST(snapshot)

def vm_vmrun():
	def run(vmx, auth='', param=None):
		vmrun = r'C:\Program Files (x86)\VMware\VMware VIX\vmrun.exe'

		from subprocess import Popen

		cmd = '"{0}" {1} {2} "{3}"'.format(vmrun, auth, param, vmx)
		print '[exec] : {0}'.format(cmd)

		proc = Popen(cmd, shell=True)
		proc.wait()

	vmx = r'D:\VMs\vmware\chu-15.04\chu-15.04.vmx'

	run(vmx, auth='-T ws', param='start')
	run(vmx, auth='-T ws', param='getGuestIPAddress')

#TEST(vm_pysphere)
#TEST(vm_vixpy)
#TEST(vm_vmrun)

