# -*- coding: utf-8 -*-

from initializer import Initializer
from util import Util

class IService:
	def __init__(self):
		self.init   = Initializer()
		self.config = self.init.config
		self.util   = self.init.util
		self.logger = self.init.logger

