# -*- coding: utf-8 -*-
import smtplib

from iservice import IService
from email.mime.text import MIMEText

class Auth:
	def __init__(self, smtpConfig):
		authConfig = smtpConfig['auth']

		self.required = authConfig['required']
		self.username = authConfig['username']
		self.password = authConfig['password']

		if self.required:
			self.prompt()

	def prompt(self):
		if not self.username:
			self.username = raw_input('Username: ')

		if not self.password:
			import getpass
			self.password = getpass.getpass()

	def login(self, smtp):
		smtp.login(self.username, self.password)

class Mailer(IService):
	def __init__(self):
		IService.__init__(self)

		smtpConfig = self.init.config['smtp']

		self.ssl  = smtpConfig['ssl' ]
		self.host = smtpConfig['host']
		self.port = smtpConfig['port']

		self.auth = Auth(smtpConfig)

	@property
	def client(self):
		if self.ssl:
			return smtplib.SMTP_SSL
		else:
			return smtplib.SMTP

	def send(self, mailForm):
		"""
		mailForm = {
			'from': 'alice@alice.com',
			'to': [
				'bob@bob.com',
				'Charlie <charlie@charlie.com>',
				...
			],
			'subject': 'e-mail title',
			'content': 'e-mail content'
		}
		"""

		if not self.host:
			return

		# check items
		criticalItems = ('from', 'to', 'subject', 'content')
		for item in criticalItems:
			if item not in mailForm:
				raise Exception('mailing form DOES NOT contain {0}'.format(item))

		# must
		sender    = mailForm['from']
		receivers = mailForm['to']
		subject   = mailForm['subject']
		content   = mailForm['content']

		# optional
		subType  = mailForm.get('subtype', 'plain')
		cc       = mailForm.get('cc', [])

		# check type of to-address
		if not isinstance(receivers, (list, set, tuple)):
			return

		smtp = self.client(self.host, self.port)

		if self.auth.required:
			self.auth.login(smtp)

		mime            = MIMEText(content, _subtype=subType, _charset='UTF-8')
		mime['From'   ] = sender
		mime['To'     ] = ', '.join(receivers)
		mime['Subject'] = subject
		mime['Cc'     ] = ', '.join(cc)

		smtp.sendmail(sender, receivers, mime.as_string())
		smtp.quit()
