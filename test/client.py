import json
import httplib
import sys

this, method, url = sys.argv[0:3]

body = None
if len(sys.argv) > 3:
	body = open(sys.argv[3], 'rb').read()

headers = {'Content-Type': 'application/json'}

h = httplib.HTTPConnection('localhost', 80)
h.request(method.upper(), url, headers=headers, body=body)

r = h.getresponse()

for hdr in r.getheaders():
	print hdr

print r.status, r.reason
print r.read()

