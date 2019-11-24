# -*- coding: utf-8 -*-
import glob
import os
import shutil
import threading

from iservice import IService

Hypervisor = None

class VirtualMachineManager(IService):
	CLONE_SUFFIX        = '-cl'
	CLONE_SNAPSHOT_NAME = 'cloned'

	def __init__(self):
		IService.__init__(self)

		self.requiredFiles = []

		self.localWorkspace   = self.init.config['task']['workspace']
		self.enabled          = self.init.config['virtualization']['enable']
		self.configFile       = self.init.config['virtualization']['config']
		self.backupDir        = self.init.config['virtualization']['backup']
		self.configLock       = threading.Lock()
		self.cloningLock      = threading.Lock()
		self.lastModifiedTime = 0

		self.maxClone     = 0
		self.guestRoot    = ''
		self.cloneRoot    = ''
		self.guestList    = {}
		self.sharedFolder = []

		self.setRequiredFiles()

		if self.enabled:
			from util import VirtualMachine
			global Hypervisor
			Hypervisor = VirtualMachine

	def check(self):
		if not self.enabled:
			raise ValueError('virtualization is not enabled')

	def setRequiredFiles(self):
		self.requiredFiles = [
			os.path.abspath('task/worker.py'),
			os.path.abspath('task/state.py')
		]

		self.requiredFiles.extend(glob.glob(os.path.join('tools', '*')))

	def isModified(self):
		with self.configLock:
			modifiedTime = os.path.getmtime(self.configFile)
			if self.lastModifiedTime < modifiedTime:
				return True
			else:
				return False

	def load(self):
		with self.configLock:
			config = self.util.jsonfile(self.configFile).load()

			self.maxClone     = config['max-clone']
			path              = config['path']
			self.guestRoot    = os.path.abspath(path['guest'])
			self.cloneRoot    = os.path.abspath(path['clone'])
			self.guestList    = config['guest-list']
			self.sharedFolder = config['shared-folder']

			"""
			# deprecated
			try:
				cliTool = os.path.abspath(config['cli-tool'])
				Hypervisor.setCommandLineTool(cliTool)
			except:
				pass
			"""

	def exists(self, guestName):
		return guestName in self.guestList

	def checkExist(self, guestName):
		if not self.exists(guestName):
			raise KeyError('virtual machine "{0}" not found'.format(guestName))

	def getGuestPath(self, guestName):
		path = self.guestList[guestName]['path']
		full = os.path.join(self.guestRoot, path)
		return os.path.abspath(full)

	def getClonePath(self, guestName, index):
		# <guest-name>#<N>
		name = '{0}{1}{2}'.format(guestName, VirtualMachineManager.CLONE_SUFFIX, index)

		# <guest-name>#<N>/<guest-name>#<N>.vmx
		subpath = os.path.join(name, '{0}.vmx'.format(name))
		path    = os.path.join(self.cloneRoot, subpath)

		# <clone-path>/<guest-name>#<N>/<guest-name>#<N>.vmx
		return os.path.abspath(path)

	def getAvailableClonePath(self, guestName):
		if self.isModified():
			self.load()

		self.checkExist(guestName)

		guest = self.getGuestPath(guestName)
		self.logger.debug('vm-guest: {0}'.format(guest))

		for index in range(1, self.maxClone + 1):
			with self.cloningLock:
				clone = self.getClonePath(guestName, index)

				# DO NOT combine these if-statements
				if os.path.isfile(clone):
					if Hypervisor(clone).isIdle():
						self.logger.info('{0} is idle'.format(clone))
						return clone
					else:
						self.logger.debug('{0} is busy'.format(clone))
						continue
				else:
					# cloned-guest naming convention
					# <guest-name>-cl<N>
					self.logger.debug('cloning {0} ...'.format(clone))
					self.open(guest, guestName).clone(clone)

					self.logger.debug('taking a snapshot {0} ...'.format(clone))
					self.open(clone, guestName).snapshot(VirtualMachineManager.CLONE_SNAPSHOT_NAME)

					return clone

		raise Exception('no more available virtual machine')

	def convertPath(self, fullPath, srcRoot, dstRoot, srcSep, dstSep):
		subPath  = fullPath[len(srcRoot) + 1:]
		replaced = subPath.replace(srcSep, dstSep)
		return '{0}{1}{2}'.format(dstRoot, dstSep, replaced)

	def convertPathLocalToRemote(self, fullPath, srcRoot, dstRoot, sep):
		# full   = c:\a\b\c\d.txt, /a/b/c/d.txt
		# local  = c:\a\b        , /a/b
		# remote = c:\e          , /e
		# return = c:\e\c\d.txt  , /e/c/d.txt
		return self.convertPath(fullPath, srcRoot, dstRoot, os.path.sep, sep)

	def convertPathRemoteToLocal(self, fullPath, srcRoot, dstRoot, sep):
		# full   = c:\e\c\d.txt  , /e/c/d.txt
		# remote = c:\e          , /e
		# local  = c:\a\b        , /a/b
		# return = c:\a\b\c\d.txt, /a/b/c/d.txt
		return self.convertPath(fullPath, srcRoot, dstRoot, sep, os.path.sep)

	def copyTaskToVM(self, vm, taskName, seq):
		sep      = vm.sep
		remoteWs = sep.join((vm.home, os.path.basename(self.localWorkspace)))

		localTask  = os.path.abspath(os.path.join(self.localWorkspace, taskName))
		backupDir  = os.path.join(localTask, self.backupDir)

		# mkdir
		remoteTask = sep.join((remoteWs, taskName))
		self.logger.debug('remote task path: {0}'.format(remoteTask))

		vm.mkdir(remoteWs)
		vm.mkdir(remoteTask)

		# log file will not be copied
		logFile = '{0}@{1}.log'.format(taskName, seq)

		# copy files temporally
		#  i.e., worker, state ...
		temporallyCopied = []
		for f in self.requiredFiles:
			self.logger.debug('temporally copy: {0} => {1}'.format(f, localTask))
			shutil.copy(f, localTask)

			base = os.path.basename(f)
			path = os.path.join(localTask, base)
			temporallyCopied.append(path)

		# upload
		for root, dirs, files in os.walk(localTask):
			for name in dirs:
				# get local and remote path
				localPath  = os.path.join(root, name)
				remotePath = self.convertPathLocalToRemote(localPath, localTask, remoteTask, sep)

				# ignore
				if localPath.startswith(backupDir):
					continue

				self.logger.debug('mkdir ==VM==> {0} '.format(remotePath))
				vm.mkdir(remotePath)

			for name in files:
				# ignored
				if logFile in name:
					continue

				# get local and remote path
				localPath  = os.path.join(root, name)
				remotePath = self.convertPathLocalToRemote(localPath, localTask, remoteTask, sep)

				# ignore
				if localPath.startswith(backupDir):
					continue

				# copy
				self.logger.debug('{0} ==VM==> {1}'.format(localPath, remotePath))
				vm.copyToGuest(localPath, remotePath)

		# clean up files copied temporally
		for path in temporallyCopied:
			self.logger.debug('remove temporally copied file, {0}'.format(path))
			os.remove(path)

		# return uploaded path
		return remoteTask

	def copyTaskFromVM(self, vm, taskName, seq, remotePath):
		sep      = vm.sep
		remoteWs = sep.join((vm.home, os.path.basename(self.localWorkspace)))

		localTask  = os.path.abspath(os.path.join(self.localWorkspace, taskName))
		backupDir  = os.path.join(localTask, self.backupDir)

		# mkdir
		if not os.path.isdir(backupDir):
			os.makedirs(backupDir)

		remoteTask = sep.join((remoteWs, taskName))
		localPath = self.convertPathRemoteToLocal(remotePath, remoteTask, backupDir, sep)

		dirPath = os.path.dirname(localPath)
		if not os.path.isdir(dirPath):
			self.logger.debug('mkdir ======> {0} '.format(dirPath))
			os.makedirs(dirPath)

		# download
		self.logger.debug('{0} ======> {1}'.format(remotePath, localPath))
		vm.copyFromGuest(remotePath, localPath)

	def getPythonPathInVM(self, vm):
		delim  = ';' if vm.isWindows else ':'
		sep    = vm.sep

		python = 'python'
		if vm.isWindows:
			python += '.exe'

		paths = vm.getenv('PATH').split(delim)
		for path in paths:
			if path.endswith(vm.sep):
				sep = ''
			else:
				sep = vm.sep

			target = '{0}{1}{2}'.format(path, sep, python)
			if vm.isfile(target):
				return target

		raise Exception('python was not found')

	def open(self, vmcfg, guestName):
		self.logger.debug('open: {0}'.format(vmcfg))

		vm = Hypervisor(vmcfg)
		vm.guestName = guestName

		return vm

	def openIdleVM(self, guestName):
		clone = self.getAvailableClonePath(guestName)
		vm    = self.open(clone, guestName)

		return vm

	def on(self, vm):
		if vm is None:
			return

		self.logger.debug('boot: {0}'.format(vm.config))
		vm.on()

	def off(self, vm):
		if vm is None:
			return

		self.logger.debug('shutdown: {0}'.format(vm.config))
		vm.off()

	def prepareVM(self, vm):
		# get configurations
		guest     = self.guestList[vm.guestName]
		desc      = guest['desc']
		system    = guest['system']
		isWindows = system['is-windows']
		home      = system['home']
		auth      = system['auth']
		username  = auth['username']
		password  = auth['password']

		vm.login(username, password)

		# following fields are not member of util.vm.VirtualMachine
		vm.isWindows = isWindows
		vm.sep       = '\\' if vm.isWindows else '/'
		vm.home      = home
		vm.desc      = desc

		self.setSharedFolders(vm)

	def runTask(self, vm, taskName, seq):
		uploadedPath = self.copyTaskToVM(vm, taskName, seq)

		sep    = vm.sep
		python = self.getPythonPathInVM(vm)
		worker = sep.join((uploadedPath, 'worker.py'))
		script = sep.join((uploadedPath, '{0}.py'.format(taskName)))

		prog   = python
		args   = '{0} {1} {2}'.format(worker, script, seq)
		self.logger.debug('{0} {1}'.format(prog, args))

		vm.run(prog, args)

	def setSharedFolders(self, vm):
		vm.sharedFolder.enable()

		# get shard folder properties of guest
		guestSharedFolderNames = [name for name, path, _writableFlag in vm.sharedFolder]

		for sharedCfg in self.sharedFolder:
			name     = sharedCfg['name']
			path     = sharedCfg['path']
			writable = sharedCfg['writable']

			if name in guestSharedFolderNames:
				continue

			self.logger.debug('add shared folder: "{0}" => "{1}" with{2} writability'
							  ''.format(name, path, '' if writable else 'out'))

			vm.sharedFolder.add(name, path, writable)

