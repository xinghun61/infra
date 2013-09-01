#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ast
import datetime
import hashlib
import hmac
import json
import os
import random
import time
import unittest

import app
from third_party.BeautifulSoup.BeautifulSoup import BeautifulSoup


TEST_DIR = os.path.join(os.path.dirname(__file__), 'tests')


class GaeTestCase(unittest.TestCase):
  def setUp(self, *args, **kwargs):
    self.clear_datastore()
    super(GaeTestCase, self).setUp(*args, **kwargs)

  # R0201: 21,2:GaeTestCase._load_content: Method could be a function
  # pylint: disable=R0201
  def _load_content(self, test_dir, path):
    with open(os.path.join(test_dir, path)) as fh:
      return fh.read()
    return None

  @staticmethod
  def save_page(localpath, content):
    page_data = {}
    page_data['content'] = content
    fetch_timestamp = datetime.datetime.now()
    model = app.Page(localpath=localpath, content=None,
                     fetch_timestamp=fetch_timestamp)
    model.put()
    app.save_page(model, localpath=localpath, fetch_timestamp=fetch_timestamp,
                  page_data=page_data)
    return model

  @staticmethod
  def clear_datastore():
    from google.appengine.api import apiproxy_stub_map, datastore_file_stub
    from google.appengine.api import memcache

    # See http://code.google.com/p/gaeunit/issues/detail?id=15 for clue.
    for key in ['datastore', 'datastore_v3']:
      # W0212: 23,16:GaeTestCase.clear_datastore: Access to a protected member
      # _APIProxyStubMap__stub_map of a client class
      # pylint: disable=W0212
      # E1101: 50,16:GaeTestCase.clear_datastore: Instance of 'APIProxyStubMap'
      # has no '_APIProxyStubMap__stub_map' member
      # pylint: disable=E1101
      if key in apiproxy_stub_map.apiproxy._APIProxyStubMap__stub_map:
        # W0212: 24,12:GaeTestCase.clear_datastore: Access to a protected
        # member _APIProxyStubMap__stub_map of a client class
        # pylint: disable=W0212
        # E1101: 54,12:GaeTestCase.clear_datastore: Instance of
        # 'APIProxyStubMap' has no '_APIProxyStubMap__stub_map' member
        # pylint: disable=E1101
        del apiproxy_stub_map.apiproxy._APIProxyStubMap__stub_map[key]

    # Use a fresh stub datastore.
    stub = datastore_file_stub.DatastoreFileStub(
        app.APP_NAME, '/dev/null', '/dev/null')
    apiproxy_stub_map.apiproxy.RegisterStub('datastore', stub)

    # Flush memcache.
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
    content = 'a' * 10**6  # ~1MB of a single character (ASCII).
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
    times = 2 * 10**6  # ~2 MB worth.
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
    times = 2 * 10**6  # ~2 MB worth.
    localpath = 'testfoo'  # The app prepends /p/.
    content = '\xe2' * times
    self.save_page(localpath=localpath, content=content)
    testapp = TestApp(handler.application)
    response = testapp.get('/p/testfoo')
    self.assertEquals('200 OK', response.status)
    # Note that content is not equal to '\xef\xbf\xbd'*times.
    self.assertEquals(content.decode('utf-8', 'replace').encode('utf-8'),
                      response.body)

  def test_app_bogus_query_string(self):
    from webtest import TestApp
    from webtest import AppError
    import handler
    localpath = 'test'  # The app prepends /p/.
    content = 'Test Query.'
    self.save_page(localpath=localpath, content=content)
    testapp = TestApp(handler.application)

    # Verify that the path with the bogus query string throws a 404.
    try:
      response = testapp.get('/p/test?query')
    except AppError, e:
      self.assertEquals(e.args[0],
          'Bad response: 404 Not Found (not 200 OK or 3xx redirect for '
          'http://localhost/p/test?query)\n')

    # Verify that the path without the bogus query string works.
    response = testapp.get('/p/test')
    self.assertEquals('200 OK', response.status)
    self.assertEquals('Test Query.', response.body)

class ConsoleTestCase(GaeTestCase):
  def test_console_handler(self):
    test_dir = os.path.join(TEST_DIR, 'test_console_handler')
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
    input_console = self._load_content(test_dir, 'console-input.html')
    expected_console = self._load_content(test_dir, 'console-expected.html')
    page_data = {'content': input_console}
    actual_console = app.console_handler(
        unquoted_localpath='chromium/console',
        remoteurl='http://build.chromium.org/p/chromium/console',
        page_data=page_data)
    # Uncomment if deeper inspection is needed of the returned console.
    # with open(os.path.join(test_dir, 'console-expected.html'), 'w') as fh:
    #   fh.write(actual_console['content'])
    self.assertEquals(expected_console, actual_console['content'],
                      'Unexpected console output found')

  def test_console_handler_utf8(self):
    test_dir = os.path.join(TEST_DIR, 'test_console_handler_utf8')
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
    input_console = self._load_content(test_dir, 'console-input.html')
    expected_console = self._load_content(test_dir, 'console-expected.html')
    page_data = {'content': input_console}
    actual_console = app.console_handler(
        unquoted_localpath='chromium/console',
        remoteurl='http://build.chromium.org/p/chromium/console',
        page_data=page_data)
    # Uncomment if deeper inspection is needed of the returned console.
    # with open(os.path.join(test_dir, 'console-expected.html'), 'w') as fh:
    #   fh.write(actual_console['content'])
    self.assertEquals(expected_console, actual_console['content'],
                      'Unexpected console output found')

  def test_parse_master(self):
    test_dir = os.path.join(TEST_DIR, 'test_parse_master')
    expected_rev = self._load_content(test_dir, 'expected-rev.html').strip()
    expected_name = self._load_content(test_dir, 'expected-name.html').strip()
    expected_status = self._load_content(test_dir,
                                         'expected-status.html').strip()
    expected_comment = self._load_content(test_dir,
                                          'expected-comment.html').strip()
    expected_details = self._load_content(test_dir,
                                          'expected-details.html').strip()
    expected_summary = self._load_content(test_dir,
                                          'expected-summary.html').strip()
    input_console = self._load_content(test_dir, 'console-input-handled.html')
    page_data = {'content': input_console}
    test_localpath = 'chromium/console'
    # Parse master returns its input, so we throw that away and access
    # the stored rows directly.
    app.parse_master(
        localpath=test_localpath,
        remoteurl='http://build.chromium.org/p/chromium/console',
        page_data=page_data)
    test_revision = '121192'
    actual_row = app.get_and_cache_rowdata(test_localpath + '/' + test_revision)
    actual_summary = app.get_and_cache_pagedata(test_localpath + '/summary')
    self.assertEquals(expected_rev, actual_row['rev'],
                      'Unexpected revision number found')
    self.assertEquals(expected_name, actual_row['name'],
                      'Unexpected revision author found')
    self.assertEquals(expected_status, actual_row['status'],
                      'Unexpected build status found')
    self.assertEquals(expected_comment, actual_row['comment'],
                      'Unexpected commit message found')
    self.assertEquals(expected_details, actual_row['details'],
                      'Unexpected build details found')
    self.assertEquals(expected_summary, actual_summary['content'],
                      'Unexpected build summary found')

  def test_parse_master_utf8(self):
    test_dir = os.path.join(TEST_DIR, 'test_parse_master_utf8')
    expected_rev = self._load_content(test_dir, 'expected-rev.html').strip()
    expected_name = self._load_content(test_dir, 'expected-name.html').strip()
    expected_status = self._load_content(test_dir,
                                         'expected-status.html').strip()
    expected_comment = self._load_content(test_dir,
                                          'expected-comment.html').strip()
    expected_details = self._load_content(test_dir,
                                          'expected-details.html').strip()
    expected_summary = self._load_content(test_dir,
                                          'expected-summary.html').strip()
    input_console = self._load_content(test_dir, 'console-input-handled.html')
    page_data = {'content': input_console}
    test_localpath = 'chromium/console'
    # Parse master returns its input, so we throw that away and access
    # the stored rows directly.
    app.parse_master(
        localpath=test_localpath,
        remoteurl='http://build.chromium.org/p/chromium/console',
        page_data=page_data)
    test_revision = '121192'
    actual_row = app.get_and_cache_rowdata(test_localpath + '/' + test_revision)
    actual_summary = app.get_and_cache_pagedata(test_localpath + '/summary')
    self.assertEquals(expected_rev.decode('utf-8'), actual_row['rev'],
                      'Unexpected revision number found')
    self.assertEquals(expected_name.decode('utf-8'), actual_row['name'],
                      'Unexpected revision author found')
    self.assertEquals(expected_status.decode('utf-8'), actual_row['status'],
                      'Unexpected build status found')
    self.assertEquals(expected_comment.decode('utf-8'), actual_row['comment'],
                      'Unexpected commit message found')
    self.assertEquals(expected_details.decode('utf-8'), actual_row['details'],
                      'Unexpected build details found')
    self.assertEquals(expected_summary.decode('utf-8'),
                      actual_summary['content'],
                      'Unexpected build summary found')

  def test_console_merger(self):
    # Read in all the necessary input files.
    test_dir = os.path.join(TEST_DIR, 'test_console_merger')
    test_masters = ['linux', 'mac', 'win', 'memory']
    filenames = ['latest_rev.txt', 'surroundings_input.html']
    for master in test_masters:
      filenames += ['%s_categories_input.html' % master,
                    '%s_summary_input.html' % master,
                    '%s_row_input.txt' % master]
    filenames.append('merged_console_output.html')
    files = {}
    for filename in filenames:
      files[filename] = self._load_content(test_dir, filename)

    # Save the input files as the corresponding pages and rows.
    test_rev = files['latest_rev.txt'].strip()
    app.memcache.set(key='latest_rev', value=test_rev)
    self.save_page(localpath='surroundings',
                   content=files['surroundings_input.html'])
    for master in test_masters:
      self.save_page('chromium.%s/console/categories' % master,
                     files['%s_categories_input.html' % master])
      self.save_page('chromium.%s/console/summary' % master,
                     files['%s_summary_input.html' % master])
      row_data = ast.literal_eval(files['%s_row_input.txt' % master])
      row_data['fetch_timestamp'] = app.datetime.datetime.now()
      app.save_row(row_data, 'chromium.%s/console/%s' % (master, test_rev))

    # Get the expected and real output, compare.
    self.save_page('merged_output', files['merged_console_output.html'])
    app.console_merger(
        'chromium/console', '', {},
        masters_to_merge=[
            'chromium.linux',
            'chromium.mac',
            'chromium.win',
            'chromium.memory',
        ],
        num_rows_to_merge=1)
    actual_mergedconsole = app.get_and_cache_pagedata('chromium/console')
    # Uncomment if deeper inspection is needed of the returned console.
    # import logging
    # logging.debug('foo')
    # with open(os.path.join(test_dir, 'merged_console_output.html'),
    #           'w') as fh:
    #   fh.write(actual_mergedconsole['content'])
    # import code
    # code.interact(local=locals())
    self.assertEquals(files['merged_console_output.html'],
                      actual_mergedconsole['content'],
                      'Unexpected console output found')

  def test_console_merger_splitrevs(self):
    # Read in all the necessary input files.
    test_dir = os.path.join(TEST_DIR, 'test_console_merger_splitrevs')
    test_masters = ['linux', 'mac']
    filenames = ['latest_rev.txt', 'surroundings_input.html']
    for master in test_masters:
      filenames += ['%s_categories_input.html' % master,
                    '%s_summary_input.html' % master,
                    '%s_row_input.txt' % master]
    filenames.append('merged_console_output.html')
    files = {}
    for filename in filenames:
      files[filename] = self._load_content(test_dir, filename)

    # Save the input files as the corresponding pages and rows.
    test_rev = files['latest_rev.txt'].strip()
    app.memcache.set(key='latest_rev', value=test_rev)
    self.save_page(localpath='surroundings',
                   content=files['surroundings_input.html'])
    for master in test_masters:
      self.save_page('chromium.%s/console/categories' % master,
                     files['%s_categories_input.html' % master])
      self.save_page('chromium.%s/console/summary' % master,
                     files['%s_summary_input.html' % master])
      row_data = ast.literal_eval(files['%s_row_input.txt' % master])
      row_data['fetch_timestamp'] = app.datetime.datetime.now()
      app.save_row(row_data, 'chromium.%s/console/%s' % (master, test_rev))

    # Get the expected and real output, compare.
    self.save_page('merged_output', files['merged_console_output.html'])
    app.console_merger(
        'chromium/console', '', {},
        masters_to_merge=[
            'chromium.linux',
            'chromium.mac',
        ],
        num_rows_to_merge=1)
    actual_mergedconsole = app.get_and_cache_pagedata('chromium/console')
    # Uncomment if deeper inspection is needed of the returned console.
    # import logging
    # logging.debug('foo')
    # with open(os.path.join(test_dir, 'merged_console_output.html'),
    #           'w') as fh:
    #   fh.write(actual_mergedconsole['content'])
    # import code
    # code.interact(local=locals())
    self.assertEquals(files['merged_console_output.html'],
                      actual_mergedconsole['content'],
                      'Unexpected console output found')


class FetchTestCase(GaeTestCase):
  class FakeResponse(object):
    status_code = 200
    content = None

  def test_fetch_direct(self):
    test_dir = os.path.join(TEST_DIR, 'test_fetch_direct')

    def fetch_url(url):
      fr = FetchTestCase.FakeResponse()
      if url == 'http://build.chromium.org/p/chromium/console':
        fr.content = self._load_content(test_dir, 'input.html')
      return fr

    expected_content = self._load_content(test_dir, 'expected.html')
    app.fetch_page(
        localpath='chromium/console',
        remoteurl='http://build.chromium.org/p/chromium/console',
        maxage=0,
        fetch_url=fetch_url)
    page = app.get_and_cache_pagedata('chromium/console')
    # Uncomment if deeper inspection is needed of the returned console.
    # with open(os.path.join(test_dir, 'expected.html'), 'w') as fh:
    #   fh.write(page['content'])
    self.assertEquals(expected_content, page['content'])

  def test_fetch_console(self):
    test_dir = os.path.join(TEST_DIR, 'test_fetch_console')

    def fetch_url(url):
      fr = FetchTestCase.FakeResponse()
      if url == 'http://build.chromium.org/p/chromium/console':
        fr.content = self._load_content(test_dir, 'input.html')
      return fr

    expected_content = self._load_content(test_dir, 'expected.html')
    app.fetch_page(
        localpath='chromium/console',
        remoteurl='http://build.chromium.org/p/chromium/console',
        maxage=0,
        postfetch=app.console_handler,
        fetch_url=fetch_url)
    page = app.get_and_cache_pagedata('chromium/console')
    # Uncomment if deeper inspection is needed of the returned console.
    # with open(os.path.join(test_dir, 'expected.html'), 'w') as fh:
    #   fh.write(page['content'])
    self.assertEquals('interface', page['body_class'])
    self.assertEquals(expected_content, page['content'])
    self.assertEquals(
        'http://build.chromium.org/p/chromium/console/../',
        page['offsite_base'])
    self.assertEquals('BuildBot: Chromium', page['title'])


class MailTestCase(GaeTestCase):
  def setUp(self):
    self.test_dir = os.path.join(TEST_DIR, 'test_mailer')
    with open(os.path.join(self.test_dir, 'input.json')) as f:
      self.input_json = json.load(f)
    self.build_data = json.loads(self.input_json['message'])

  @staticmethod
  def _hash_message(mytime, message, url, secret):
    salt = random.getrandbits(32)
    hasher = hmac.new(secret, message, hashlib.sha256)
    hasher.update(str(mytime))
    hasher.update(str(salt))
    client_hash = hasher.hexdigest()

    return {'message': message,
            'time': mytime,
            'salt': salt,
            'url': url,
            'hmac-sha256': client_hash,
           }

  def test_html_format(self):
    import gatekeeper_mailer
    template = gatekeeper_mailer.MailTemplate(self.build_data['waterfall_url'],
                                              self.build_data['build_url'],
                                              self.build_data['project_name'],
                                              'test@chromium.org')

    _, html_content, _ = template.genMessageContent(self.build_data)

    with open(os.path.join(self.test_dir, 'expected.html')) as f:
      expected_html = ' '.join(f.read().splitlines())

    saw = str(BeautifulSoup(html_content)).split()
    expected = str(BeautifulSoup(expected_html)).split()

    self.assertEqual(saw, expected)

  def test_hmac_validation(self):
    from mailer import Email
    message = self.input_json['message']
    url = 'http://invalid.chromium.org'
    secret = 'pajamas'

    test_json = self._hash_message(time.time(), message, url, secret)
    # pylint: disable=W0212
    self.assertTrue(Email._validate_message(test_json, url, secret))

    # Test that a trailing slash doesn't affect URL parsing.
    test_json = self._hash_message(time.time(), message, url + '/', secret)
    # pylint: disable=W0212
    self.assertTrue(Email._validate_message(test_json, url, secret))

    tests = [
        self._hash_message(time.time() + 61, message, url, secret),
        self._hash_message(time.time() - 61, message, url, secret),
        self._hash_message(time.time(), message, url + 'hey', secret),
        self._hash_message(time.time(), message, url, secret + 'hey'),
    ]

    for test_json in tests:
      # pylint: disable=W0212
      self.assertFalse(Email._validate_message(test_json, url, secret))

    test_json = self._hash_message(time.time(), message, url, secret)
    test_json['message'] = test_json['message'] + 'hey'
    # pylint: disable=W0212
    self.assertFalse(Email._validate_message(test_json, url, secret))
