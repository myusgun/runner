# -*- coding: utf-8 -*-
import os
import threading

from iservice import IService
from task import state

def getToday():
	from datetime import datetime as dt
	return dt.now().date()

class Statistics(IService):
	def __init__(self):
		IService.__init__(self)

		self.statisticsFile = self.init.config['statistics']['info']
		self.statistics = {}
		self.lock = threading.Lock()

		if not os.path.isfile(self.statisticsFile) or os.stat(self.statisticsFile).st_size == 0:
			self.save()

		self.load()

	def load(self):
		with self.lock:
			self.statistics = self.util.jsonfile(self.statisticsFile).load()

	def save(self):
		with self.lock:
			self.util.jsonfile(self.statisticsFile).save(self.statistics)

	def get(self):
		return self.statistics

	def set(self, taskName, seq, stateCode):
		"""
		{
			task: {
				seq: {
					total: {
						state1: 0,
						state2: 1,
						...
					},
					year: {
						# for each months
						[
							# for each days ...
							[
								{
									state1: 0,
									state2: 1,
									...
								},
								...
							],
							...
						]
					}
				}
			}
		}
		"""

		stateName   = state.asString(stateCode)

		today       = getToday()
		twoYearsAgo = str(today.year - 2)
		year        = str(today.year)
		month       = str(today.month)
		day         = str(today.day)

		with self.lock:
			if taskName not in self.statistics:
				self.statistics[taskName] = {}

			if seq not in self.statistics[taskName]:
				self.statistics[taskName][seq] = {}

			# clean up old data
			if twoYearsAgo in self.statistics[taskName][seq]:
				del self.statistics[taskName][seq][twoYearsAgo]

			if year not in self.statistics[taskName][seq]:
				self.statistics[taskName][seq][year] = {}

			if month not in self.statistics[taskName][seq][year]:
				self.statistics[taskName][seq][year][month] = {}

			if day not in self.statistics[taskName][seq][year][month]:
				self.statistics[taskName][seq][year][month][day] = {}

			if stateName not in self.statistics[taskName][seq][year][month][day]:
				self.statistics[taskName][seq][year][month][day][stateName] = 0

		self.statistics[taskName][seq][year][month][day][stateName] += 1

		self.save()

