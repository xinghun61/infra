#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import os
import unittest

import app


class GaeTestCase(unittest.TestCase):
  def setUp(self, *args, **kwargs):
    self.clear_datastore()
    super(GaeTestCase, self).setUp(*args, **kwargs)

  @staticmethod
  def save_page(localpath, content):
    fetch_timestamp = datetime.datetime.now()
    model = app.Page(localpath=localpath, content=None,
                     fetch_timestamp=fetch_timestamp)
    model.put()
    app.save_page(model, localpath=localpath, content=content,
                  fetch_timestamp=fetch_timestamp)
    return model

  @staticmethod
  def clear_datastore():
    from google.appengine.api import apiproxy_stub_map, datastore_file_stub
    from google.appengine.api import memcache

    # See http://code.google.com/p/gaeunit/issues/detail?id=15 for clue.
    for key in ['datastore', 'datastore_v3']:
      # W0212: 23,16:GaeTestCase.clear_datastore: Access to a protected member
      # _APIProxyStubMap__stub_map of a client class
      # E1101: 26,16:GaeTestCase.clear_datastore: Instance of 'APIProxyStubMap'
      # has no '_APIProxyStubMap__stub_map' member
      # pylint: disable=W0212,E1101
      if key in apiproxy_stub_map.apiproxy._APIProxyStubMap__stub_map:
        # W0212: 24,12:GaeTestCase.clear_datastore: Access to a protected
        # member _APIProxyStubMap__stub_map of a client class
        # E1101: 30,12:GaeTestCase.clear_datastore: Instance of
        # 'APIProxyStubMap' has no '_APIProxyStubMap__stub_map' member
        # pylint: disable=W0212,E1101
        del apiproxy_stub_map.apiproxy._APIProxyStubMap__stub_map[key]

    # Use a fresh stub datastore.
    stub = datastore_file_stub.DatastoreFileStub(
        app.APP_NAME, '/dev/null', '/dev/null')
    apiproxy_stub_map.apiproxy.RegisterStub('datastore', stub)

    # Flush memcache.
    # E1101: 42,4:GaeTestCase.clear_datastore: Module
    # 'google.appengine.api.memcache' has no 'flush_all' member
    # pylint: disable=E1101
    memcache.flush_all()

class MainTestCase(GaeTestCase):
  def test_main_page_redirect(self):
    from webtest import TestApp
    import handler
    testapp = TestApp(handler.application)
    response = testapp.get('/')
    self.assertEquals('302 Moved Temporarily', response.status)
    self.assertEquals('', response.body)

class PageTestCase(GaeTestCase):
  def test_creation(self):
    fetch_timestamp = datetime.datetime.now()
    localpath = 'test'  # The app prepends /p/.
    content = 'Test.'
    model = app.Page(fetch_timestamp=fetch_timestamp,
                     localpath=localpath, content=content)
    model.put()
    fetched_model = app.Page.all().filter('localpath =', localpath).fetch(1)[0]
    self.assertEquals(fetched_model.content, content)

class AppTestCase(GaeTestCase):
  def test_app(self):
    from webtest import TestApp
    import handler
    localpath = 'test'  # The app prepends /p/.
    content = 'Test.'
    self.save_page(localpath=localpath, content=content)
    testapp = TestApp(handler.application)
    response = testapp.get('/p/test')
    self.assertEquals('200 OK', response.status)
    self.assertEquals('Test.', response.body)

  def test_app_blob(self):
    from webtest import TestApp
    import handler
    localpath = 'testfoo'  # The app prepends /p/.
    content = 'a' * 1024*1024  # 1MB of a single character (ASCII).
    self.save_page(localpath=localpath, content=content)
    testapp = TestApp(handler.application)
    response = testapp.get('/p/testfoo')
    self.assertEquals('200 OK', response.status)
    self.assertEquals(content, response.body)

  def test_app_unicode(self):
    from webtest import TestApp
    import handler
    localpath = 'testfoo'  # The app prepends /p/.
    content = u'\ua000'  # A single character Unicode character.
    self.save_page(localpath=localpath, content=content)
    testapp = TestApp(handler.application)
    response = testapp.get('/p/testfoo')
    self.assertEquals('200 OK', response.status)
    # u'\ua000'.encode('utf-8') == '\xea\x80\x80'
    self.assertEquals('\xea\x80\x80', response.body)

  def test_app_unicode_blob(self):
    from webtest import TestApp
    import handler
    times = 1024*1024*2  # 2 MB worth.
    localpath = 'testfoo'  # The app prepends /p/.
    content = u'\ua000' * times  # Lots of a single Unicode character.
    self.save_page(localpath=localpath, content=content)
    testapp = TestApp(handler.application)
    response = testapp.get('/p/testfoo')
    self.assertEquals('200 OK', response.status)
    # u'\ua000'.encode('utf-8') == '\xea\x80\x80'
    self.assertEquals('\xea\x80\x80' * times, response.body)

  def test_app_cp1252(self):
    from webtest import TestApp
    import handler
    localpath = 'testfoo'  # The app prepends /p/.
    content = '\xe2'
    self.save_page(localpath=localpath, content=content)
    testapp = TestApp(handler.application)
    response = testapp.get('/p/testfoo')
    self.assertEquals('200 OK', response.status)
    # '\xe2'.decode('utf-8', 'replace').encode('utf-8') == '\xef\xbf\xbd'
    self.assertEquals('\xef\xbf\xbd', response.body)

  def test_app_cp1252_blob(self):
    from webtest import TestApp
    import handler
    times = 1024*1024*2  # 2 MB worth.
    localpath = 'testfoo'  # The app prepends /p/.
    content = '\xe2' * times
    self.save_page(localpath=localpath, content=content)
    testapp = TestApp(handler.application)
    response = testapp.get('/p/testfoo')
    self.assertEquals('200 OK', response.status)
    # Note that content is not equal to '\xef\xbf\xbd'*times.
    self.assertEquals(content.decode('utf-8', 'replace').encode('utf-8'),
                      response.body)

  def test_app_query_string(self):
    from webtest import TestApp
    from webtest import AppError
    import handler
    localpath = 'test?query'  # The app prepends /p/.
    content = 'Test Query.'
    self.save_page(localpath=localpath, content=content)
    testapp = TestApp(handler.application)

    # Verify that the path without the query string throws a 404.
    try:
      response = testapp.get('/p/test')
    except AppError, e:
      self.assertEquals(e.args[0],
          'Bad response: 404 Not Found (not 200 OK or 3xx redirect for '
          'http://localhost/p/test)\n')

    # Verify that the path with the query string works.
    response = testapp.get('/p/test?query')
    self.assertEquals('200 OK', response.status)
    self.assertEquals('Test Query.', response.body)

class ConsoleTestCase(GaeTestCase):
  def test_console_handler(self):
    test_dir = os.path.join(os.path.dirname(__file__),
                            'tests',
                            'test_console_handler')
    self.save_page(localpath='chromium/sheriff.js',
                   content='document.write(\'sheriff1\')')
    self.save_page(localpath='chromium/sheriff_webkit.js',
                   content='document.write(\'sheriff2\')')
    self.save_page(localpath='chromium/sheriff_memory.js',
                   content='document.write(\'sheriff3\')')
    self.save_page(localpath='chromium/sheriff_nacl.js',
                   content='document.write(\'sheriff4\')')
    self.save_page(localpath='chromium/sheriff_perf.js',
                   content='document.write(\'sheriff5\')')
    self.save_page(localpath='chromium/sheriff_cros_mtv.js',
                   content='document.write(\'sheriff6, sheriff7\')')
    self.save_page(localpath='chromium/sheriff_cros_nonmtv.js',
                   content='document.write(\'sheriff8\')')
    with open(os.path.join(test_dir, 'console-input.html')) as input_fh:
      input_console = input_fh.read()
    with open(os.path.join(test_dir, 'console-expected.html')) as expected_fh:
      expected_console = expected_fh.read()
    actual_console = app.console_handler(
        unquoted_localpath='chromium/console',
        remoteurl='http://build.chromium.org/p/chromium/console',
        content=input_console)
    # Uncomment if deeper inspection is needed of the returned console.
    # with open(os.path.join(test_dir, 'console-expected.html'), 'w') as fh:
    #   fh.write(actual_console)
    self.assertEquals(expected_console, actual_console,
                      'Unexpected console output found')

  def test_console_handler_utf8(self):
    test_dir = os.path.join(os.path.dirname(__file__),
                            'tests',
                            'test_console_handler_utf8')
    self.save_page(localpath='chromium/sheriff.js',
                   content='document.write(\'sheriff1\')')
    self.save_page(localpath='chromium/sheriff_webkit.js',
                   content='document.write(\'sheriff2\')')
    self.save_page(localpath='chromium/sheriff_memory.js',
                   content='document.write(\'sheriff3\')')
    self.save_page(localpath='chromium/sheriff_nacl.js',
                   content='document.write(\'sheriff4\')')
    self.save_page(localpath='chromium/sheriff_perf.js',
                   content='document.write(\'sheriff5\')')
    self.save_page(localpath='chromium/sheriff_cros_mtv.js',
                   content='document.write(\'sheriff6, sheriff7\')')
    self.save_page(localpath='chromium/sheriff_cros_nonmtv.js',
                   content='document.write(\'sheriff8\')')
    with open(os.path.join(test_dir, 'console-input.html')) as input_fh:
      input_console = input_fh.read()
    with open(os.path.join(test_dir, 'console-expected.html')) as expected_fh:
      expected_console = expected_fh.read()
    actual_console = app.console_handler(
        unquoted_localpath='chromium/console',
        remoteurl='http://build.chromium.org/p/chromium/console',
        content=input_console)
    # Uncomment if deeper inspection is needed of the returned console.
    # with open(os.path.join(test_dir, 'console-expected.html'), 'w') as fh:
    #   fh.write(actual_console)
    self.assertEquals(expected_console, actual_console,
                      'Unexpected console output found')

  def test_console_merger(self):
    test_dir = os.path.join(os.path.dirname(__file__),
                            'tests',
                            'test_console_merger')
    filedata = {}
    for filename in [
        'chromium_chrome_console_input.html',
        'chromium_chromiumos_console_input.html',
        'chromium_main_console_input.html',
        'chromium_memory_console_input.html',
        'chromium_merged_console.html',
    ]:
      with open(os.path.join(test_dir, filename)) as fh:
        filedata[filename] = fh.read()
    self.save_page(localpath='chromium.chrome/console',
                   content=filedata['chromium_chrome_console_input.html'])
    self.save_page(localpath='chromium.chromiumos/console',
                   content=filedata['chromium_chromiumos_console_input.html'])
    self.save_page(localpath='chromium.main/console',
                   content=filedata['chromium_main_console_input.html'])
    self.save_page(localpath='chromium.memory/console',
                   content=filedata['chromium_memory_console_input.html'])
    actual_mergedconsole = app.console_merger(
        'chromium.main/console',
        'http://build.chromium.org/p/chromium/console',
        content=filedata['chromium_merged_console.html'])
    # Uncomment if deeper inspection is needed of the returned console.
    # import logging
    # logging.debug('foo')
    # with open(os.path.join(test_dir, 'chromium_merged_console.html'),
    #           'w') as fh:
    #   fh.write(actual_mergedconsole)
    # import code
    # code.interact(local=locals())
    self.assertEquals(filedata['chromium_merged_console.html'],
                      actual_mergedconsole,
                      'Unexpected console output found')

  def test_console_merger_utf8(self):
    test_dir = os.path.join(os.path.dirname(__file__),
                            'tests',
                            'test_console_merger_utf8')
    filedata = {}
    for filename in [
        'chromium_chrome_console_input.html',
        'chromium_chromiumos_console_input.html',
        'chromium_main_console_input.html',
        'chromium_memory_console_input.html',
        'chromium_merged_console.html',
    ]:
      with open(os.path.join(test_dir, filename)) as fh:
        filedata[filename] = fh.read()
    self.save_page(localpath='chromium.chrome/console',
                   content=filedata['chromium_chrome_console_input.html'])
    self.save_page(localpath='chromium.chromiumos/console',
                   content=filedata['chromium_chromiumos_console_input.html'])
    self.save_page(localpath='chromium.main/console',
                   content=filedata['chromium_main_console_input.html'])
    self.save_page(localpath='chromium.memory/console',
                   content=filedata['chromium_memory_console_input.html'])
    actual_mergedconsole = app.console_merger(
        'chromium.main/console',
        'http://build.chromium.org/p/chromium/console',
        content=filedata['chromium_merged_console.html'])
    # Uncomment if deeper inspection is needed of the returned console.
    # import logging
    # logging.debug('foo')
    # merged_path = os.path.join(test_dir, 'chromium_merged_console.html')
    # with open(merged_path, 'w') as fh:
    #   fh.write(actual_mergedconsole)
    # import code
    # code.interact(local=locals())
    self.assertEquals(filedata['chromium_merged_console.html'],
                      actual_mergedconsole,
                      'Unexpected console output found')

  def test_console_merger_splitrevs(self):
    test_dir = os.path.join(os.path.dirname(__file__),
                            'tests',
                            'test_console_merger_splitrevs')
    filedata = {}
    for filename in [
        'chromium_chrome_console.html',
        'chromium_chromiumos_console.html',
        'chromium_console.html',
        'chromium_memory_console.html',
        'chromium_merged_console.html',
    ]:
      with open(os.path.join(test_dir, filename)) as fh:
        filedata[filename] = fh.read()
    self.save_page(localpath='chromium.chrome/console',
                   content=filedata['chromium_chrome_console.html'])
    self.save_page(localpath='chromium.chromiumos/console',
                   content=filedata['chromium_chromiumos_console.html'])
    self.save_page(localpath='chromium.main/console',
                   content=filedata['chromium_console.html'])
    self.save_page(localpath='chromium.memory/console',
                   content=filedata['chromium_memory_console.html'])
    actual_mergedconsole = app.console_merger(
        'chromium.main/console',
        'http://build.chromium.org/p/chromium/console',
        content=filedata['chromium_merged_console.html'])
    # Uncomment if deeper inspection is needed of the returned console.
    # import logging
    # logging.debug('foo')
    # with open(os.path.join(test_dir, 'chromium_merged_console.html'),
    #           'w') as fh:
    #   fh.write(actual_mergedconsole)
    # import code
    # code.interact(local=locals())
    self.assertEquals(filedata['chromium_merged_console.html'],
                      actual_mergedconsole,
                      'Unexpected console output found')
