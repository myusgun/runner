# -*- coding: utf-8 -*-
import httplib
import json
import os
import re
import sys
import threading
import time
import urllib2

SERVER = 'localhost' # FIXME 'unsigned.kr'

# --------------------------------------------------------------
# Common
# --------------------------------------------------------------
def to_string(obj):
	try:
		import collections

		if isinstance(obj, basestring):
			return str(obj)
		elif isinstance(obj, collections.Mapping):
			return dict(map(to_string, obj.iteritems()))
		elif isinstance(obj, collections.Iterable):
			return type(obj)(map(to_string, obj))
		else:
			return obj
	except:
		return obj

def request(host, method, url, request_body=None):
	headers = {'Content-Type': 'application/json'}

	req_body = None
	if request_body:
		req_body = json.dumps(request_body)

	http = httplib.HTTPConnection(host)
	http.request(method, url, req_body, headers=headers)

	resp = http.getresponse()
	if resp.status != 200:
		raise RuntimeError(resp.status, resp.reason, resp.read())

	resp_body = resp.read()
	if resp_body:
		return to_string(json.loads(resp_body))
	else:
		return resp_body

def post_multipart(url, f):
	import importlib

	dirname  = os.path.dirname(__file__)
	basename = os.path.basename(__file__)
	mod, _   = os.path.splitext(basename)

	if dirname not in sys.path:
		sys.path.append(dirname)

	this = importlib.import_module(mod)

	register_openers = getattr(this, 'register_openers')
	multipart_encode = getattr(this, 'multipart_encode')

	register_openers()
	datagen, headers = multipart_encode({'file': f})
	req = urllib2.Request(url, datagen, headers)
	urllib2.urlopen(req)

# --------------------------------------------------------------
# Service
# --------------------------------------------------------------
GET_ALL_TASKS, \
GET_TASK_SEQ, \
REGISTER_TASK, \
REMOVE_TASK, \
GET_TASK, \
RUN_TASK, \
STOP_TASK, \
GET_TASK_FILE_LIST, \
DOWNLOAD_TASK_FILE, \
UPLOAD_TASK_FILE, \
DELETE_TASK_FILE, \
= range(11)

URL = {
# url map
#
# <name>: [<method>, <url>]
#
GET_ALL_TASKS       : ['GET'   , '/api?tasks'                   ],
GET_TASK_SEQ        : ['GET'   , '/api/<task>'                  ],
REGISTER_TASK       : ['PUT'   , '/api/<task>'                  ],
REMOVE_TASK         : ['DELETE', '/api/<task>/<seq>'            ],
GET_TASK            : ['GET'   , '/api/<task>/<seq>'            ],
RUN_TASK            : ['POST'  , '/api/<task>/<seq>/run'        ],
STOP_TASK           : ['POST'  , '/api/<task>/<seq>/stop'       ],
GET_TASK_FILE_LIST  : ['GET'   , '/api/file/<task>'             ],
DOWNLOAD_TASK_FILE  : ['GET'   , '/api/file/<task>?path='       ],
UPLOAD_TASK_FILE    : ['POST'  , '/api/file/<task>?subdir='     ],
DELETE_TASK_FILE    : ['DELETE', '/api/file/<task>'             ],
}

def get_url(key):
	return list(URL[key])

def replace_task(url, name):
	return url.replace('<task>', name)

def replace_seq(url, seq):
	return url.replace('<seq>', seq)

def get_seq(name):
	url = get_url(GET_TASK_SEQ)
	url[1] = replace_task(url[1], name)

	return request(SERVER, *url).keys()[0]

def get_task(key, name=None, include_seq=True):
	url = get_url(key)

	if name:
		url[1] = replace_task(url[1], name)

		if include_seq:
			url[1] = replace_seq(url[1], get_seq(name))

	return url

def req(key, name=None, body=None, include_seq=True):
	method, url = get_task(key, name=name, include_seq=include_seq)

	return request(SERVER, method, url, request_body=body)

class ICallback:
	def __init__(self, f, path, size):
		self.f = f
		self.path = path
		self.size = size

	def prepare(self):
		pass

	def succeed(self):
		pass

	def failed(self):
		pass

class CallbackClasses:
	Upload = ICallback
	Download = ICallback

def upload_task_file(name, path, subdir=''):
	__method, url = get_task(UPLOAD_TASK_FILE, name, include_seq=False)

	url = 'http://{0}{1}{2}'.format(SERVER, url, subdir)

	f = open(path, 'rb')

	callback = None
	if CallbackClasses.Upload:
		callback = CallbackClasses.Upload(f, path, os.path.getsize(path))

	try:
		if callback:
			callback.prepare()

		post_multipart(url, f)

		if callback:
			callback.succeed()

	except:
		if callback:
			callback.failed()

		raise

	finally:
		f.close()

def upload_task_dir(name, path):
	for directory, _sub, files in os.walk(path):
		for filename in files:
			filepath = os.path.join(directory, filename)
			subdir   = os.path.dirname(filepath)[len(path) + 1:]
			_size    = os.path.getsize(filepath)

			upload_task_file(name, filepath, subdir)

def upload_task(name, path):
	path = os.path.abspath(path)
	upload_task_dir(name, path)

def delete_task(name):
	req(DELETE_TASK_FILE, name, include_seq=False)

def download_task_file(name, remote, local=None):
	__method, url = get_task(DOWNLOAD_TASK_FILE, name, include_seq=False)

	url = 'http://{0}{1}{2}'.format(SERVER, url, remote)

	url_lib = urllib2.urlopen(url)
	meta    = url_lib.info()
	size    = int(meta.getheaders('Content-Length')[0])

	BLOCK_SIZE = 8192
	written    = 0

	if not local:
		local = os.path.join(os.path.abspath(name), remote)

	dirname = os.path.dirname(local)
	if not dirname:
		dirname = os.path.abspath('.')

	if not os.path.isdir(dirname):
		os.makedirs(dirname)

	f = open(local, 'wb')

	callback = None
	if CallbackClasses.Download:
		callback = CallbackClasses.Download(f, remote, size)

	try:
		if callback:
			callback.prepare()

		while written < size:
			content = url_lib.read(BLOCK_SIZE)
			written += len(content)
			f.write(content)

		if callback:
			callback.succeed()

		if f:
			f.close()

	except:
		if callback:
			callback.failed()

		if f:
			f.close()

		if os.path.isfile(local):
			os.remove(local)

		raise

# --------------------------------------------------------------
# API
# --------------------------------------------------------------
error = None

def __result(arg=None):
	global error

	if isinstance(arg, Exception):
		error = arg
		return False

	else:
		error = None
		if arg is not None:
			return arg
		else:
			return True

def getAllTasks():
	try:
		ret = req(GET_ALL_TASKS).keys()

		return __result(ret)
	except Exception as e:
		return __result(e)

def registerTask(name, path=None):
	try:
		tasks = getAllTasks()
		if tasks is False: # DO NOT use 'not tasks' for '[]'
			return False

		if name in tasks:
			raise KeyError('task [{0}] is already registered'.format(name))

		if path:
			upload_task(name, path)

		req(REGISTER_TASK, name, include_seq=False)

		return __result()
	except Exception as e:
		return __result(e)

def removeTask(name):
	try:
		try:
			req(REMOVE_TASK, name)

		except RuntimeError as e:
			# (404, 'NOT FOUND', ...
			#  ~~~
			msg  = str(e)
			code = int(msg[1:4])

			# not found ?
			if code == 404:
				pass
			else:
				raise

		except:
			raise

		delete_task(name)

		return __result()
	except Exception as e:
		return __result(e)

def manageTask(name, command):
	funcs = {
		'register': registerTask,
		'remove': removeTask,
	}

	lower_cmd = command.lower()

	if lower_cmd not in funcs:
		raise Exception('unknown management command: {0}'.format(command))

	return funcs[lower_cmd](name)

def getTask(name):
	try:
		obj = {
			'info': req(GET_TASK, name),
			'file': req(GET_TASK_FILE_LIST, name)
		}

		return __result(obj)
	except Exception as e:
		return __result(e)

def runTask(name):
	try:
		req(RUN_TASK, name)

		return __result()
	except Exception as e:
		return __result(e)

def stopTask(name):
	try:
		req(STOP_TASK, name)

		return __result()
	except Exception as e:
		return __result(e)

def controlTask(name, command):
	funcs = {
		'run': runTask,
		'stop': stopTask,
	}

	lower_cmd = command.lower()

	if lower_cmd not in funcs:
		raise Exception('unknown management command: {0}'.format(command))

	return funcs[lower_cmd](name)

def download(name, remote, local=None):
	try:
		download_task_file(name, remote, local)

		return __result()
	except Exception as e:
		return __result(e)

def __traverse_response(dic):
	ret = []

	for dirname, _entries in dic['dir'].iteritems():
		files = __traverse_response(dic['dir'][dirname])
		joined = [os.path.join(dirname, filename) for filename in files]
		ret.extend(joined)

	ret.extend(dic['file'])

	return ret

def download_regex(name, regex, local=None):
	try:
		files = getTask(name)['file']
		files = __traverse_response(files)

		for remote in files:
			if re.match(regex, remote):
				download_task_file(name, remote, local)

		return __result()
	except Exception as e:
		return __result(e)

# --------------------------------------------------------------
# for Command-line
# --------------------------------------------------------------
def omit(s, limit):
	if len(s) > limit:
		s = '{0} ...'.format(s[:limit - 4])

	return s

def fixed_width(s, limit):
	omitted = omit(s, limit)
	blank = ' ' * (limit - len(s))

	return omitted, blank

class NameOnlyCallback(ICallback):
	def __init__(self, f, path, size):
		ICallback.__init__(self, f, path, size)

	def prepare(self):
		max_path = 70
		self.omitted, self.blank = fixed_width(self.path, max_path)
		print '>> {0}'.format(self.omitted),

	def succeed(self):
		print '{0} [ OK ]'.format(self.blank)

	def failed(self):
		print '{0} [FAIL]'.format(self.blank)

class ProgressCallback(ICallback):
	def __init__(self, f, path, size):
		ICallback.__init__(self, f, path, size)

		self.thread = threading.Thread(target=self.progress)
		self.is_failed = False

	def prepare(self):
		self.thread.start()

	def succeed(self):
		self.thread.join()
		print '[ OK ]'

	def failed(self):
		self.is_failed = True
		self.thread.join()
		print '[FAIL]'

	def progress(self):
		max_path = 40
		path = ''.join(fixed_width(self.path, max_path))

		max_prog = 20
		offset = 0

		prev_percentage = 0

		while offset < self.size and not self.is_failed:
			offset = self.f.tell()

			percentage = ((offset * 100) / self.size)
			prog_count = (percentage / (100 / max_prog))

			prog  = '=' * (           prog_count)
			blank = ' ' * (max_prog - prog_count)

			if percentage == prev_percentage:
				time.sleep(0)
				continue

			prev_percentage = percentage

			print '\r >> {0} [{1}{2}] {3}%'.format(path, prog, blank, percentage),

def usage():
	import inspect

	funcs = [
		getAllTasks,
		registerTask,
		removeTask,
		getTask,
		runTask,
		stopTask,
		download,
		download_regex,
	]

	print 'Usage: python {0} <command> [options]'.format(sys.argv[0])
	print '%-20s    %s' % ('Commands:', 'Options:')
	for func in funcs:
		name = '    %-20s' % func.func_name
		args = ' '.join(inspect.getargspec(func).args)
		print '{0}    {1}'.format(name, args)

if __name__ == '__main__':
	from pprint import pprint

	is_no_arg = len(sys.argv) == 1
	is_help   = '--help' in sys.argv

	if is_no_arg or is_help:
		usage()
		sys.exit(int(is_no_arg))

	CallbackClasses.Upload   = ProgressCallback
	CallbackClasses.Download = ProgressCallback

	name = sys.argv[1]
	func = getattr(sys.modules[__name__], name)

	params = sys.argv[2:]
	if params:
		resp = func(*params)
	else:
		resp = func()

	if not resp:
		print omit(str(error), 80)

	pprint(resp)


# ==============================================================
# THIRD PARTY: BEGIN {{{
# ==============================================================
# 
# http://atlee.ca/software/poster
# 
"""
License
poster is licensed under the MIT license:
Copyright (c) 2011 Chris AtLee
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

# --------------------------------------------------------------
# streaminghttp.py {{{
# --------------------------------------------------------------
"""Streaming HTTP uploads module.

This module extends the standard httplib and urllib2 objects so that
iterable objects can be used in the body of HTTP requests.

In most cases all one should have to do is call :func:`register_openers()`
to register the new streaming http handlers which will take priority over
the default handlers, and then you can use iterable objects in the body
of HTTP requests.

**N.B.** You must specify a Content-Length header if using an iterable object
since there is no way to determine in advance the total size that will be
yielded, and there is no way to reset an interator.

Example usage:

>>> from StringIO import StringIO
>>> import urllib2, poster.streaminghttp

>>> opener = poster.streaminghttp.register_openers()

>>> s = "Test file data"
>>> f = StringIO(s)

>>> req = urllib2.Request("http://localhost:5000", f,
...                       {'Content-Length': str(len(s))})
"""

import httplib, urllib2, socket
from httplib import NotConnected

"""
__all__ = ['StreamingHTTPConnection', 'StreamingHTTPRedirectHandler',
        'StreamingHTTPHandler', 'register_openers']

if hasattr(httplib, 'HTTPS'):
    __all__.extend(['StreamingHTTPSHandler', 'StreamingHTTPSConnection'])
"""

class _StreamingHTTPMixin:
    """Mixin class for HTTP and HTTPS connections that implements a streaming
    send method."""
    def send(self, value):
        """Send ``value`` to the server.

        ``value`` can be a string object, a file-like object that supports
        a .read() method, or an iterable object that supports a .next()
        method.
        """
        # Based on python 2.6's httplib.HTTPConnection.send()
        if self.sock is None:
            if self.auto_open:
                self.connect()
            else:
                raise NotConnected()

        # send the data to the server. if we get a broken pipe, then close
        # the socket. we want to reconnect when somebody tries to send again.
        #
        # NOTE: we DO propagate the error, though, because we cannot simply
        #       ignore the error... the caller will know if they can retry.
        if self.debuglevel > 0:
            print "send:", repr(value)
        try:
            blocksize = 8192
            if hasattr(value, 'read') :
                if hasattr(value, 'seek'):
                    value.seek(0)
                if self.debuglevel > 0:
                    print "sendIng a read()able"
                data = value.read(blocksize)
                while data:
                    self.sock.sendall(data)
                    data = value.read(blocksize)
            elif hasattr(value, 'next'):
                if hasattr(value, 'reset'):
                    value.reset()
                if self.debuglevel > 0:
                    print "sendIng an iterable"
                for data in value:
                    self.sock.sendall(data)
            else:
                self.sock.sendall(value)
        except socket.error, v:
            if v[0] == 32:      # Broken pipe
                self.close()
            raise

class StreamingHTTPConnection(_StreamingHTTPMixin, httplib.HTTPConnection):
    """Subclass of `httplib.HTTPConnection` that overrides the `send()` method
    to support iterable body objects"""

class StreamingHTTPRedirectHandler(urllib2.HTTPRedirectHandler):
    """Subclass of `urllib2.HTTPRedirectHandler` that overrides the
    `redirect_request` method to properly handle redirected POST requests

    This class is required because python 2.5's HTTPRedirectHandler does
    not remove the Content-Type or Content-Length headers when requesting
    the new resource, but the body of the original request is not preserved.
    """

    handler_order = urllib2.HTTPRedirectHandler.handler_order - 1

    # From python2.6 urllib2's HTTPRedirectHandler
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Return a Request or None in response to a redirect.

        This is called by the http_error_30x methods when a
        redirection response is received.  If a redirection should
        take place, return a new Request to allow http_error_30x to
        perform the redirect.  Otherwise, raise HTTPError if no-one
        else should try to handle this url.  Return None if you can't
        but another Handler might.
        """
        m = req.get_method()
        if (code in (301, 302, 303, 307) and m in ("GET", "HEAD")
            or code in (301, 302, 303) and m == "POST"):
            # Strictly (according to RFC 2616), 301 or 302 in response
            # to a POST MUST NOT cause a redirection without confirmation
            # from the user (of urllib2, in this case).  In practice,
            # essentially all clients do redirect in this case, so we
            # do the same.
            # be conciliant with URIs containing a space
            newurl = newurl.replace(' ', '%20')
            newheaders = dict((k, v) for k, v in req.headers.items()
                              if k.lower() not in (
                                  "content-length", "content-type")
                             )
            return urllib2.Request(newurl,
                           headers=newheaders,
                           origin_req_host=req.get_origin_req_host(),
                           unverifiable=True)
        else:
            raise urllib2.HTTPError(req.get_full_url(), code, msg, headers, fp)

class StreamingHTTPHandler(urllib2.HTTPHandler):
    """Subclass of `urllib2.HTTPHandler` that uses
    StreamingHTTPConnection as its http connection class."""

    handler_order = urllib2.HTTPHandler.handler_order - 1

    def http_open(self, req):
        """Open a StreamingHTTPConnection for the given request"""
        return self.do_open(StreamingHTTPConnection, req)

    def http_request(self, req):
        """Handle a HTTP request.  Make sure that Content-Length is specified
        if we're using an interable value"""
        # Make sure that if we're using an iterable object as the request
        # body, that we've also specified Content-Length
        if req.has_data():
            data = req.get_data()
            if hasattr(data, 'read') or hasattr(data, 'next'):
                if not req.has_header('Content-length'):
                    raise ValueError(
                            "No Content-Length specified for iterable body")
        return urllib2.HTTPHandler.do_request_(self, req)

if hasattr(httplib, 'HTTPS'):
    class StreamingHTTPSConnection(_StreamingHTTPMixin,
            httplib.HTTPSConnection):
        """Subclass of `httplib.HTTSConnection` that overrides the `send()`
        method to support iterable body objects"""

    class StreamingHTTPSHandler(urllib2.HTTPSHandler):
        """Subclass of `urllib2.HTTPSHandler` that uses
        StreamingHTTPSConnection as its http connection class."""

        handler_order = urllib2.HTTPSHandler.handler_order - 1

        def https_open(self, req):
            return self.do_open(StreamingHTTPSConnection, req)

        def https_request(self, req):
            # Make sure that if we're using an iterable object as the request
            # body, that we've also specified Content-Length
            if req.has_data():
                data = req.get_data()
                if hasattr(data, 'read') or hasattr(data, 'next'):
                    if not req.has_header('Content-length'):
                        raise ValueError(
                                "No Content-Length specified for iterable body")
            return urllib2.HTTPSHandler.do_request_(self, req)


def get_handlers():
    handlers = [StreamingHTTPHandler, StreamingHTTPRedirectHandler]
    if hasattr(httplib, "HTTPS"):
        handlers.append(StreamingHTTPSHandler)
    return handlers
    
def register_openers():
    """Register the streaming http handlers in the global urllib2 default
    opener object.

    Returns the created OpenerDirector object."""
    opener = urllib2.build_opener(*get_handlers())

    urllib2.install_opener(opener)

    return opener
# --------------------------------------------------------------
# }}} streaminghttp.py
# --------------------------------------------------------------

# --------------------------------------------------------------
# encode.py {{{
# --------------------------------------------------------------
"""multipart/form-data encoding module

This module provides functions that faciliate encoding name/value pairs
as multipart/form-data suitable for a HTTP POST or PUT request.

multipart/form-data is the standard way to upload files over HTTP"""

"""
__all__ = ['gen_boundary', 'encode_and_quote', 'MultipartParam',
        'encode_string', 'encode_file_header', 'get_body_size', 'get_headers',
        'multipart_encode']
"""

try:
    import uuid
    def gen_boundary():
        """Returns a random string to use as the boundary for a message"""
        return uuid.uuid4().hex
except ImportError:
    import random, sha
    def gen_boundary():
        """Returns a random string to use as the boundary for a message"""
        bits = random.getrandbits(160)
        return sha.new(str(bits)).hexdigest()

import urllib, re, os, mimetypes
try:
    from email.header import Header
except ImportError:
    # Python 2.4
    from email.Header import Header

def encode_and_quote(data):
    """If ``data`` is unicode, return urllib.quote_plus(data.encode("utf-8"))
    otherwise return urllib.quote_plus(data)"""
    if data is None:
        return None

    if isinstance(data, unicode):
        data = data.encode("utf-8")
    return urllib.quote_plus(data)

def _strify(s):
    """If s is a unicode string, encode it to UTF-8 and return the results,
    otherwise return str(s), or None if s is None"""
    if s is None:
        return None
    if isinstance(s, unicode):
        return s.encode("utf-8")
    return str(s)

class MultipartParam(object):
    """Represents a single parameter in a multipart/form-data request

    ``name`` is the name of this parameter.

    If ``value`` is set, it must be a string or unicode object to use as the
    data for this parameter.

    If ``filename`` is set, it is what to say that this parameter's filename
    is.  Note that this does not have to be the actual filename any local file.

    If ``filetype`` is set, it is used as the Content-Type for this parameter.
    If unset it defaults to "text/plain; charset=utf8"

    If ``filesize`` is set, it specifies the length of the file ``fileobj``

    If ``fileobj`` is set, it must be a file-like object that supports
    .read().

    Both ``value`` and ``fileobj`` must not be set, doing so will
    raise a ValueError assertion.

    If ``fileobj`` is set, and ``filesize`` is not specified, then
    the file's size will be determined first by stat'ing ``fileobj``'s
    file descriptor, and if that fails, by seeking to the end of the file,
    recording the current position as the size, and then by seeking back to the
    beginning of the file.

    ``cb`` is a callable which will be called from iter_encode with (self,
    current, total), representing the current parameter, current amount
    transferred, and the total size.
    """
    def __init__(self, name, value=None, filename=None, filetype=None,
                        filesize=None, fileobj=None, cb=None):
        self.name = Header(name).encode()
        self.value = _strify(value)
        if filename is None:
            self.filename = None
        else:
            if isinstance(filename, unicode):
                # Encode with XML entities
                self.filename = filename.encode("ascii", "xmlcharrefreplace")
            else:
                self.filename = str(filename)
            self.filename = self.filename.encode("string_escape").\
                    replace('"', '\\"')
        self.filetype = _strify(filetype)

        self.filesize = filesize
        self.fileobj = fileobj
        self.cb = cb

        if self.value is not None and self.fileobj is not None:
            raise ValueError("Only one of value or fileobj may be specified")

        if fileobj is not None and filesize is None:
            # Try and determine the file size
            try:
                self.filesize = os.fstat(fileobj.fileno()).st_size
            except (OSError, AttributeError):
                try:
                    fileobj.seek(0, 2)
                    self.filesize = fileobj.tell()
                    fileobj.seek(0)
                except:
                    raise ValueError("Could not determine filesize")

    def __cmp__(self, other):
        attrs = ['name', 'value', 'filename', 'filetype', 'filesize', 'fileobj']
        myattrs = [getattr(self, a) for a in attrs]
        oattrs = [getattr(other, a) for a in attrs]
        return cmp(myattrs, oattrs)

    def reset(self):
        if self.fileobj is not None:
            self.fileobj.seek(0)
        elif self.value is None:
            raise ValueError("Don't know how to reset this parameter")

    @classmethod
    def from_file(cls, paramname, filename):
        """Returns a new MultipartParam object constructed from the local
        file at ``filename``.

        ``filesize`` is determined by os.path.getsize(``filename``)

        ``filetype`` is determined by mimetypes.guess_type(``filename``)[0]

        ``filename`` is set to os.path.basename(``filename``)
        """

        return cls(paramname, filename=os.path.basename(filename),
                filetype=mimetypes.guess_type(filename)[0],
                filesize=os.path.getsize(filename),
                fileobj=open(filename, "rb"))

    @classmethod
    def from_params(cls, params):
        """Returns a list of MultipartParam objects from a sequence of
        name, value pairs, MultipartParam instances,
        or from a mapping of names to values

        The values may be strings or file objects, or MultipartParam objects.
        MultipartParam object names must match the given names in the
        name,value pairs or mapping, if applicable."""
        if hasattr(params, 'items'):
            params = params.items()

        retval = []
        for item in params:
            if isinstance(item, cls):
                retval.append(item)
                continue
            name, value = item
            if isinstance(value, cls):
                assert value.name == name
                retval.append(value)
                continue
            if hasattr(value, 'read'):
                # Looks like a file object
                filename = getattr(value, 'name', None)
                if filename is not None:
                    filetype = mimetypes.guess_type(filename)[0]
                else:
                    filetype = None

                retval.append(cls(name=name, filename=filename,
                    filetype=filetype, fileobj=value))
            else:
                retval.append(cls(name, value))
        return retval

    def encode_hdr(self, boundary):
        """Returns the header of the encoding of this parameter"""
        boundary = encode_and_quote(boundary)

        headers = ["--%s" % boundary]

        if self.filename:
            disposition = 'form-data; name="%s"; filename="%s"' % (self.name,
                    self.filename)
        else:
            disposition = 'form-data; name="%s"' % self.name

        headers.append("Content-Disposition: %s" % disposition)

        if self.filetype:
            filetype = self.filetype
        else:
            filetype = "text/plain; charset=utf-8"

        headers.append("Content-Type: %s" % filetype)

        headers.append("")
        headers.append("")

        return "\r\n".join(headers)

    def encode(self, boundary):
        """Returns the string encoding of this parameter"""
        if self.value is None:
            value = self.fileobj.read()
        else:
            value = self.value

        if re.search("^--%s$" % re.escape(boundary), value, re.M):
            raise ValueError("boundary found in encoded string")

        return "%s%s\r\n" % (self.encode_hdr(boundary), value)

    def iter_encode(self, boundary, blocksize=4096):
        """Yields the encoding of this parameter
        If self.fileobj is set, then blocks of ``blocksize`` bytes are read and
        yielded."""
        total = self.get_size(boundary)
        current = 0
        if self.value is not None:
            block = self.encode(boundary)
            current += len(block)
            yield block
            if self.cb:
                self.cb(self, current, total)
        else:
            block = self.encode_hdr(boundary)
            current += len(block)
            yield block
            if self.cb:
                self.cb(self, current, total)
            last_block = ""
            encoded_boundary = "--%s" % encode_and_quote(boundary)
            boundary_exp = re.compile("^%s$" % re.escape(encoded_boundary),
                    re.M)
            while True:
                block = self.fileobj.read(blocksize)
                if not block:
                    current += 2
                    yield "\r\n"
                    if self.cb:
                        self.cb(self, current, total)
                    break
                last_block += block
                if boundary_exp.search(last_block):
                    raise ValueError("boundary found in file data")
                last_block = last_block[-len(encoded_boundary)-2:]
                current += len(block)
                yield block
                if self.cb:
                    self.cb(self, current, total)

    def get_size(self, boundary):
        """Returns the size in bytes that this param will be when encoded
        with the given boundary."""
        if self.filesize is not None:
            valuesize = self.filesize
        else:
            valuesize = len(self.value)

        return len(self.encode_hdr(boundary)) + 2 + valuesize

def encode_string(boundary, name, value):
    """Returns ``name`` and ``value`` encoded as a multipart/form-data
    variable.  ``boundary`` is the boundary string used throughout
    a single request to separate variables."""

    return MultipartParam(name, value).encode(boundary)

def encode_file_header(boundary, paramname, filesize, filename=None,
        filetype=None):
    """Returns the leading data for a multipart/form-data field that contains
    file data.

    ``boundary`` is the boundary string used throughout a single request to
    separate variables.

    ``paramname`` is the name of the variable in this request.

    ``filesize`` is the size of the file data.

    ``filename`` if specified is the filename to give to this field.  This
    field is only useful to the server for determining the original filename.

    ``filetype`` if specified is the MIME type of this file.

    The actual file data should be sent after this header has been sent.
    """

    return MultipartParam(paramname, filesize=filesize, filename=filename,
            filetype=filetype).encode_hdr(boundary)

def get_body_size(params, boundary):
    """Returns the number of bytes that the multipart/form-data encoding
    of ``params`` will be."""
    size = sum(p.get_size(boundary) for p in MultipartParam.from_params(params))
    return size + len(boundary) + 6

def get_headers(params, boundary):
    """Returns a dictionary with Content-Type and Content-Length headers
    for the multipart/form-data encoding of ``params``."""
    headers = {}
    boundary = urllib.quote_plus(boundary)
    headers['Content-Type'] = "multipart/form-data; boundary=%s" % boundary
    headers['Content-Length'] = str(get_body_size(params, boundary))
    return headers

class multipart_yielder:
    def __init__(self, params, boundary, cb):
        self.params = params
        self.boundary = boundary
        self.cb = cb

        self.i = 0
        self.p = None
        self.param_iter = None
        self.current = 0
        self.total = get_body_size(params, boundary)

    def __iter__(self):
        return self

    def next(self):
        """generator function to yield multipart/form-data representation
        of parameters"""
        if self.param_iter is not None:
            try:
                block = self.param_iter.next()
                self.current += len(block)
                if self.cb:
                    self.cb(self.p, self.current, self.total)
                return block
            except StopIteration:
                self.p = None
                self.param_iter = None

        if self.i is None:
            raise StopIteration
        elif self.i >= len(self.params):
            self.param_iter = None
            self.p = None
            self.i = None
            block = "--%s--\r\n" % self.boundary
            self.current += len(block)
            if self.cb:
                self.cb(self.p, self.current, self.total)
            return block

        self.p = self.params[self.i]
        self.param_iter = self.p.iter_encode(self.boundary)
        self.i += 1
        return self.next()

    def reset(self):
        self.i = 0
        self.current = 0
        for param in self.params:
            param.reset()

def multipart_encode(params, boundary=None, cb=None):
    """Encode ``params`` as multipart/form-data.

    ``params`` should be a sequence of (name, value) pairs or MultipartParam
    objects, or a mapping of names to values.
    Values are either strings parameter values, or file-like objects to use as
    the parameter value.  The file-like objects must support .read() and either
    .fileno() or both .seek() and .tell().

    If ``boundary`` is set, then it as used as the MIME boundary.  Otherwise
    a randomly generated boundary will be used.  In either case, if the
    boundary string appears in the parameter values a ValueError will be
    raised.

    If ``cb`` is set, it should be a callback which will get called as blocks
    of data are encoded.  It will be called with (param, current, total),
    indicating the current parameter being encoded, the current amount encoded,
    and the total amount to encode.

    Returns a tuple of `datagen`, `headers`, where `datagen` is a
    generator that will yield blocks of data that make up the encoded
    parameters, and `headers` is a dictionary with the assoicated
    Content-Type and Content-Length headers.

    Examples:

    >>> datagen, headers = multipart_encode( [("key", "value1"), ("key", "value2")] )
    >>> s = "".join(datagen)
    >>> assert "value2" in s and "value1" in s

    >>> p = MultipartParam("key", "value2")
    >>> datagen, headers = multipart_encode( [("key", "value1"), p] )
    >>> s = "".join(datagen)
    >>> assert "value2" in s and "value1" in s

    >>> datagen, headers = multipart_encode( {"key": "value1"} )
    >>> s = "".join(datagen)
    >>> assert "value2" not in s and "value1" in s

    """
    if boundary is None:
        boundary = gen_boundary()
    else:
        boundary = urllib.quote_plus(boundary)

    headers = get_headers(params, boundary)
    params = MultipartParam.from_params(params)

    return multipart_yielder(params, boundary, cb), headers
# --------------------------------------------------------------
# }}} encode.py
# --------------------------------------------------------------

# ==============================================================
# }}} THIRD PARTY: END
# ==============================================================

