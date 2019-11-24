# -*- coding: utf-8 -*-
import os
import random
import re
import sys
import logging
from logging import handlers

from util import Util

class Initializer:
	__logger = None

	def __init__(self, seed=None):
		# fixed
		self.configFile = 'config/settings.json'

		self.util = Util()
		self.config = self.util.jsonfile(self.configFile).load()
		self.logger = self.initLogger()

		self.makeDirectories()

	def getWorkspace(self):
		return self.config['task']['workspace']

	def makeDirectories(self):
		self.util.mkdir(self.getWorkspace())

	def getLogLevel(self):
		logLevel = self.config['log']['level']

		levelMap = {
			'critical': logging.CRITICAL,
			'error'   : logging.ERROR,
			'warning' : logging.WARNING,
			'info'    : logging.INFO,
			'debug'   : logging.DEBUG,
		}

		return levelMap[logLevel]

	def initLogger(self):
		if Initializer.__logger is None:
			logFile = self.config['log']['name']

			Initializer.__logger = logging.getLogger(logFile)
			handler = logging.handlers.TimedRotatingFileHandler(logFile, when='D', backupCount=15)

			self.addLogHandler(logging.StreamHandler())
			self.addLogHandler(handler)

		return Initializer.__logger

	def addLogHandler(self, handler):
		logFormat = '[%(asctime)-15s][%(lineno)04d][%(module)s][%(funcName)s] %(message)s'
		formatter = logging.Formatter(logFormat)
		logLevel  = self.getLogLevel()

		handler.setFormatter(formatter)
		handler.setLevel(logLevel)

		Initializer.__logger.setLevel(logLevel)
		Initializer.__logger.addHandler(handler)

