# -*- coding: utf-8 -*-
import os
import sys
import glob
import json
import shutil
import logging
import urllib2
import threading
import subprocess

class _internal:
	def __init__(self):
		pass

	# GPF: General Protection Fault
	def setWindowsGPF(self, bEnable):
		if not sys.platform.startswith("win"):
			return

		import ctypes

		"""
		SetErrorMode() function
		 - see https://msdn.microsoft.com/en-us/library/windows/desktop/ms680621(v=vs.85).aspx

		GetErrorMode() function
		 - supported from Windows Vista
		 - see https://msdn.microsoft.com/en-us/library/windows/desktop/ms679355(v=vs.85).aspx

		"""

		SEM_FAILCRITICALERRORS     = 0x0001
		SEM_NOALIGNMENTFAULTEXCEPT = 0x0004
		SEM_NOGPFAULTERRORBOX      = 0x0002
		SEM_NOOPENFILEERRORBOX     = 0x8000

		isGPFEnabled = lambda flags: flags & SEM_NOGPFAULTERRORBOX == 0

		flags = ctypes.windll.kernel32.GetErrorMode();

		if isGPFEnabled(flags) and not bEnable:
			ctypes.windll.kernel32.SetErrorMode(SEM_NOGPFAULTERRORBOX)
		else:
			ctypes.windll.kernel32.SetErrorMode(flags & ~SEM_NOGPFAULTERRORBOX)

class Util:
	__logger = None

	def __init__(self):
		pass

	def addLogHandler(self, handler):
		logFormat = '[%(asctime)-15s][%(lineno)04d][%(module)s] %(message)s'
		formatter = logging.Formatter(logFormat)

		handler.setFormatter(formatter)
		handler.setLevel(logging.DEBUG)

		self.logger.setLevel(logging.DEBUG)
		self.logger.addHandler(handler)

	@property
	def logger(self):
		if Util.__logger is None:
			Util.__logger = logging.getLogger('__py_util__')
			self.addLogHandler(logging.StreamHandler())

		return Util.__logger

	def execute(self, szCmd, **kwargs):
		logging.info(szCmd)

		bReturnStdout = False

		for szKey, vValue in kwargs.iteritems():
			if szKey == 'ret_out':
				bReturnStdout = vValue
			elif szKey == 'gpf':
				_internal().setWindowsGPF(vValue)

		if bReturnStdout:
			return subprocess.check_output(szCmd, shell=True)
		else:
			proc = subprocess.Popen(szCmd, shell=True)
			return proc.wait() & 0xffffffff

	def python(self, szCmd):
		return self.execute('{0} {1}'.format(sys.executable, szCmd))

	def mkdir(self, szPath):
		if not os.path.isdir(szPath):
			os.makedirs(szPath)

	def grep(self, szNeedle, szGlob):
		dictGrep = {}

		for szFile in glob.glob(szGlob):
			if os.path.isdir(szFile):
				continue

			with open(szFile, 'rb') as clsFile:
				for nLine, szLine in enumerate(clsFile.readlines()):
					if szNeedle in szLine:
						if szFile not in dictGrep:
							dictGrep[szFile] = []

						dictGrep[szFile][nLine] = szLine

		return dictGrep

	def copy(self, szSrc, szDst):
		if os.path.isfile(szSrc):
			shutil.copy2(szSrc, szDst)
		elif os.path.isdir(szSrc):
			szBasename = os.path.basename(szSrc)
			szNewDst   = os.path.join(szDst, szBasename)

			if not os.path.isdir(szNewDst):
				self.mkdir(szNewDst)

			for szSubItem in os.listdir(szSrc):
				szSrcPath = os.path.join(	szSrc, szSubItem)
				szDstPath = os.path.join(szNewDst, szSubItem)
				self.copy(szSrcPath, szDstPath)
		else:
			for szGlob in glob.glob(szSrc):
				if os.path.isdir(szGlob):
					szBasename = os.path.basename(szGlob)
					self.copy(szGlob, os.path.join(szDst, szBasename))
				else:
					self.copy(szGlob, szDst)

	def rename(self, szSrc, szDst):
		os.renames(szSrc, szDst)

	def move(self, szSrc, szDst):
		self.rename(szSrc, szDst)

	def remove(self, szPath):
		for szOne in glob.glob(szPath):
			if os.path.isdir(szOne):
				for szSub in os.listdir(szOne):
					szSubPath = os.path.join(szOne, szSub)
					self.remove(szSubPath)
				os.rmdir(szOne)
			else:
				os.remove(szOne)

	def sizeFormat(self, nSize):
		szSuffix = "B"
		listUnit = ["", "K", "M", "G", "T", "P", "E", "Z"]

		for szUnit in listUnit:
			if abs(nSize) < 1024.0:
				return "%3.1f %s%s" % (nSize, szUnit, szSuffix)

			nSize /= 1024.0

		return "%.1f %s%s" % (nSize, "Y", szSuffix)

	def wget(self, szUrl, **kwargs):
		getIfExist = lambda szKey, valDefault: kwargs[szKey] if szKey in kwargs else valDefault

		szFileName = getIfExist('out', szUrl.split('/')[-1])
		bPrint     = getIfExist('print', True)

		clsUrl    = urllib2.urlopen(szUrl)
		clsFile   = open(szFileName, 'wb')
		clsMeta   = clsUrl.info()
		nFileSize = int(clsMeta.getheaders('Content-Length')[0])

		if bPrint:
			print '%18s / %9s] %s' % (' ', sizeFormat(nFileSize), szFileName),

		nReadSize = 0
		nBlockSize = 8192
		while True:
			abyBuffer = clsUrl.read(nBlockSize)
			if not abyBuffer:
				break

			nReadSize += len(abyBuffer)
			clsFile.write(abyBuffer)

			if bPrint:
				per = '%3.2f%%' % (nReadSize * 100. / nFileSize)
				print '\r[%7s][%9s' % (per, sizeFormat(nReadSize)),

		clsFile.close()
		print ''
		return szFileName

	def countFiles(self, szPath):
		return sum(len(f) for p, d, f in os.walk(szPath))

	class jsonfile:
		def __init__(self, path):
			self.path = path

		def load(self):
			with open(self.path, 'r') as f:
				return json.load(f)

		def save(self, obj):
			with open(self.path, 'w+') as f:
				json.dump(obj, f, sort_keys=True, indent=2)

