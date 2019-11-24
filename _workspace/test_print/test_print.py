# -*- coding: utf-8 -*-
import datetime
import os

# 프로퍼티 설정
class Property:
	# TC 설명
	desc      = 'print datetime and etc.'

	# TC 작성자
	author    = 'Alice'

	# email 알림을 받을 주소 (list 타입)
	# action()에서 raise가 발생하면 여기 나열된 메일주소로 알림 메일 발송
	email     = ['alice@unsigned.kr']

	# 가상화 플랫폼 이름
	# None 이면 가상화 하지 않음
	platform  = None

	# 반복 규칙
	# 1. None
	#  * 반복하지 않음
	# 2. 숫자 형식
	#  * N: N회 수행
	# 3. 문자열 형식
	#  * 'infinite': 무한 반복
	#  * 'HH:mm': 매일 지정된 시간에 실행
	#             ex) '23:45' => 매일 23시 45분(오후 11시 45분)에 실행
	#  * 'every <N>h': 매 <N> 시간 마다 반복
	#  * 'every <N>m': 매 <N> 분 마다 반복
	repeat    = None

	# 예외가 raise 되었을 때, 무시하고 계속 진행할지 여부 (알림 메일은 이 옵션과 무관하게 발송)
	contOnErr = True

	# 사용할 플러그인 목록
	plugins   = ['add', 'plugin_example']

	# 가상화되는 경우, 공유 폴더 마운트 경로 (자동 설정됨)
	#  AEGIS 서버의 다른 드라이브들에 접근할 수 있는 root 경로
	mount     = ''

	# 가상화되는 경우, TC 실행 후 자동 백업할 대상
	backup    = ['test_print.stdout']

# TC의 "동작"을 정의하기 위한 action() 함수
# 가급적 1회에 수행할 동작을 작성하고 Property.repeat 을 통해 반복 수행하도록 구성하는 것을 권장
#
# 'do'인자는 함수이며, 키워드 인자(kwargs)를 받아 해당 기능을 실행
def action(do):
	# TC action() 작성 예시
	# stdout 및 stderr 는 <Task 이름>.stdout 파일에 저장됨

	# plugin 사용
	plugin_example = do(plugin='plugin_example')
	print 'plugin_example.do_something(\'test name\', 123) =', plugin_example.do_something('test name', 123)

	# process 실행
	#  dump 옵션으로 crash dump 생성 여부를 결정 (기본값: False)
	#  기다리지 않고 즉시 return하는 경우, wait=False
	now = str(datetime.datetime.utcnow())
	res = do(process=['date', '/t'], dump=False, shell=True)
	print '{0} = {1}'.format(now[:10], res[1])

	print do(process=['dir'], dump=False, shell=True)[1]

	# 메일 송신
	# 폼 만들기 (from, to, subject, content)
	mail_form = {
		'from': 'bob@unsigned.kr',
		'to': ['dcp520@naver.com'],
		'subject': 'test mail title',
		'content': 'test mail content'
	}
	# 송신
	do(mail=mail_form)

if __name__ == '__main__':
	# TC 작성자가 정상동작하는지를 테스트하기 위해
	# do() 함수를 dummy로 주고 실행함
	action(lambda **kwargs: str(kwargs))

