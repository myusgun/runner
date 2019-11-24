# -*- coding: utf-8 -*-
raise DeprecationWarning()

import subprocess

class VMRun:
	EXECUTABLE = ''

	@staticmethod
	def setExecutable(path):
		VMRun.EXECUTABLE = path

	def run(self, auth=None, cmd=None, params=[]):
		cmdlist = [VMRun.EXECUTABLE]

		if auth:
			cmdlist.extend(auth)

		if cmd:
			cmdlist.extend(cmd)

		if params:
			cmdlist.extend(params)

		return subprocess.check_output(cmdlist)

	def __init__(self, vmx):
		self.vmx = vmx

	def start(self):
		self.run(cmd='start', params=['nogui'])

	def stop(self):
		pass

	def reset(self):
		pass

	def pause(self):
		pass

	def resume(self):
		pass

	def suspend(self):
		pass

	def snapshot(self, snapshotName):
		pass

	def revertToSnapshot(self, snapshotName=None):
		pass

	def deleteSnapshot(self, snapshotName):
		pass

	def runProgram(self, path, args=None, noWait=False, activeWindow=False, interactive=False):
		pass

	def fileExistsInGuest(self, path):
		pass

	def directoryExistsInGuest(self, path):
		pass

	def addSharedFolder(self, name, path):
		pass

	def removeSharedFolder(self, name):
		pass

	def enableSharedFolders(self, name):
		pass

	def disableSharedFolders(self, name):
		pass

	def listProcessesInGuest(self):
		pass

	def killProcessInGuest(self, pid):
		pass

	def runScriptInGuest(self, interpreter, scriptText, noWait=False, activeWindow=False, interactive=False):
		pass

	def createDirectoryInGuest(self, path):
		pass

	def deleteDirectoryInGuest(self, path):
		pass

	def copyFileFromHostToGuest(self, src, dst):
		pass

	def copyFileFromGuestToHost(self, src, dst):
		pass

	def captureScreen(self, path):
		pass

	def getIPAddress(self):
		raise NotImplementedError('check vmware version')
		return self.run(cmd='getGuestIPAddress', params=['-wait'])

	def clone(self, dst, isFull=True):
		creationType = 'full' if isFull else 'linked'
		return self.run(cmd=['clone', self.vmx], params=[dst, creationType])

"""

vmrun version 1.15.2 build-3272444

Usage: vmrun [AUTHENTICATION-FLAGS] COMMAND [PARAMETERS]



AUTHENTICATION-FLAGS
--------------------
These must appear before the command and any command parameters.

   -h <hostName>  (not needed for Workstation)
   -P <hostPort>  (not needed for Workstation)
   -T <hostType> (ws|server|server1|fusion|esx|vc|player)
     for example, use '-T server' for Server 2.0
                  use '-T server1' for Server 1.0
                  use '-T ws' for VMware Workstation
                  use '-T ws-shared' for VMware Workstation (shared mode)
                  use '-T esx' for VMware ESX
                  use '-T vc' for VMware vCenter Server
   -u <userName in host OS>  (not needed for Workstation)
   -p <password in host OS>  (not needed for Workstation)
   -vp <password for encrypted virtual machine>
   -gu <userName in guest OS>
   -gp <password in guest OS>



POWER COMMANDS           PARAMETERS           DESCRIPTION
--------------           ----------           -----------
start                    Path to vmx file     Start a VM or Team
                         [gui|nogui]

stop                     Path to vmx file     Stop a VM or Team
                         [hard|soft]

reset                    Path to vmx file     Reset a VM or Team
                         [hard|soft]

suspend                  Path to vmx file     Suspend a VM or Team
                         [hard|soft]

pause                    Path to vmx file     Pause a VM

unpause                  Path to vmx file     Unpause a VM



SNAPSHOT COMMANDS        PARAMETERS           DESCRIPTION
-----------------        ----------           -----------
listSnapshots            Path to vmx file     List all snapshots in a VM
                         [showTree]

snapshot                 Path to vmx file     Create a snapshot of a VM
                         Snapshot name

deleteSnapshot           Path to vmx file     Remove a snapshot from a VM
                         Snapshot name
                         [andDeleteChildren]

revertToSnapshot         Path to vmx file     Set VM state to a snapshot
                         Snapshot name



GUEST OS COMMANDS        PARAMETERS           DESCRIPTION
-----------------        ----------           -----------
runProgramInGuest        Path to vmx file     Run a program in Guest OS
                         [-noWait]
                         [-activeWindow]
                         [-interactive]
                         Complete-Path-To-Program
                         [Program arguments]

fileExistsInGuest        Path to vmx file     Check if a file exists in Guest OS
                         Path to file in guest

directoryExistsInGuest   Path to vmx file     Check if a directory exists in Guest OS
                         Path to directory in guest

setSharedFolderState     Path to vmx file     Modify a Host-Guest shared folder
                         Share name
                         Host path
                         writable | readonly

addSharedFolder          Path to vmx file     Add a Host-Guest shared folder
                         Share name
                         New host path

removeSharedFolder       Path to vmx file     Remove a Host-Guest shared folder
                         Share name

enableSharedFolders      Path to vmx file     Enable shared folders in Guest
                         [runtime]

disableSharedFolders     Path to vmx file     Disable shared folders in Guest
                         [runtime]

listProcessesInGuest     Path to vmx file     List running processes in Guest OS

killProcessInGuest       Path to vmx file     Kill a process in Guest OS
                         process id

runScriptInGuest         Path to vmx file     Run a script in Guest OS
                         [-noWait]
                         [-activeWindow]
                         [-interactive]
                         Interpreter path
                         Script text

deleteFileInGuest        Path to vmx file     Delete a file in Guest OS
Path in guest

createDirectoryInGuest   Path to vmx file     Create a directory in Guest OS
Directory path in guest

deleteDirectoryInGuest   Path to vmx file     Delete a directory in Guest OS
Directory path in guest

CreateTempfileInGuest    Path to vmx file     Create a temporary file in Guest OS

listDirectoryInGuest     Path to vmx file     List a directory in Guest OS
                         Directory path in guest

CopyFileFromHostToGuest  Path to vmx file     Copy a file from host OS to guest OS
Path on host             Path in guest


CopyFileFromGuestToHost  Path to vmx file     Copy a file from guest OS to host OS
Path in guest            Path on host


renameFileInGuest        Path to vmx file     Rename a file in Guest OS
                         Original name
                         New name

captureScreen            Path to vmx file     Capture the screen of the VM to a local file
Path on host

writeVariable            Path to vmx file     Write a variable in the VM state
                         [runtimeConfig|guestEnv|guestVar]
                         variable name
                         variable value

readVariable             Path to vmx file     Read a variable in the VM state
                         [runtimeConfig|guestEnv|guestVar]
                         variable name

getGuestIPAddress        Path to vmx file     Gets the IP address of the guest
                         [-wait]



GENERAL COMMANDS         PARAMETERS           DESCRIPTION
----------------         ----------           -----------
list                                          List all running VMs

upgradevm                Path to vmx file     Upgrade VM file format, virtual hw

installTools             Path to vmx file     Install Tools in Guest

checkToolsState          Path to vmx file     Check the current Tools state

register                 Path to vmx file     Register a VM

unregister               Path to vmx file     Unregister a VM

listRegisteredVM                              List registered VMs

deleteVM                 Path to vmx file     Delete a VM

clone                    Path to vmx file     Create a copy of the VM
                         Path to destination vmx file
                         full|linked
                         [-snapshot=Snapshot Name]
                         [-cloneName=Name]




Examples:


Starting a virtual machine with Workstation on a Windows host
   vmrun -T ws start "c:\my VMs\myVM.vmx"


Stopping a virtual machine on an ESX host
   vmrun -T esx -h https://myHost.com/sdk -u hostUser -p hostPassword stop "[storage1] vm/myVM.vmx"


Running a program in a virtual machine with Workstation on a Windows host with Windows guest
   vmrun -T ws -gu guestUser -gp guestPassword runProgramInGuest "c:\my VMs\myVM.vmx" "c:\Program Files\myProgram.exe"


Running a program in a virtual machine with Server on a Linux host with Linux guest
   vmrun -T server -h https://myHost.com:8333/sdk -u hostUser -p hostPassword -gu guestUser -gp guestPassword runProgramInGuest "[standard] vm/myVM.vmx" /usr/bin/X11/xclock -display :0


Creating a snapshot of a virtual machine with Workstation on a Windows host
   vmrun -T ws snapshot "c:\my VMs\myVM.vmx" mySnapshot


Reverting to a snapshot with Workstation on a Windows host
   vmrun -T ws revertToSnapshot "c:\my VMs\myVM.vmx" mySnapshot


Deleting a snapshot with Workstation on a Windows host
   vmrun -T ws deleteSnapshot "c:\my VMs\myVM.vmx" mySnapshot


Enabling Shared Folders with Workstation on a Windows host
   vmrun -T ws enableSharedFolders "c:\my VMs\myVM.vmx"

"""

