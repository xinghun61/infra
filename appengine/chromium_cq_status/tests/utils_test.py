# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from tests.testing_utils import testing
from shared import utils


class MockWebApp(object):
  def __init__(self):
    self.response = MockResponse()

class MockResponse(object):
  def __init__(self):
    self.body = ''
    self.headers = MockHeaders()

  def write(self, text):
    self.body += text

class MockHeaders(object):
  def __init__(self):
    self.is_cross_origin = False
    self.is_json_content = False

  def add_header(self, key, value): # pragma: no cover
    if key == "Access-Control-Allow-Origin":
      self.is_cross_origin = (value == "*")
    elif key == 'Content-Type':
      self.is_json_content = (value == 'application/json')

class TestUtils(testing.AppengineTestCase):
  def test_filter_dict(self):
    self.assertEquals(
        {'b': 2, 'c': 3},
        utils.filter_dict({'a': 1, 'b': 2, 'c': 3}, ('b', 'c', 'd')))

  def test_is_valid_user(self):
    self.assertFalse(utils.is_valid_user())

    self.mock_current_user('random', 'random@person.com')
    self.assertFalse(utils.is_valid_user())

    self.mock_current_user('real', 'real@chromium.org')
    self.assertTrue(utils.is_valid_user())

    self.mock_current_user('real', 'real@google.com')
    self.assertTrue(utils.is_valid_user())

    self.mock_current_user('fake', 'fake@google.comm')
    self.assertFalse(utils.is_valid_user())

    self.mock_current_user('fake', 'fake@google_com')
    self.assertFalse(utils.is_valid_user())

    self.mock_current_user('fake', 'fake@chromium.orgg')
    self.assertFalse(utils.is_valid_user())

    self.mock_current_user('fake', 'fake@chromium_org')
    self.assertFalse(utils.is_valid_user())

  def test_password_sha1(self):
    self.assertEquals(
        '018d644a17b71b65cef51fa0a523a293f2b3266f',
        utils.password_sha1('cq'))

  def test_to_unix_timestamp(self):
    self.assertEquals(100,
        utils.to_unix_timestamp(datetime.utcfromtimestamp(100)))
    self.assertEquals(100.1,
        utils.to_unix_timestamp(datetime.utcfromtimestamp(100.1)))
    self.assertEquals(100.5,
        utils.to_unix_timestamp(datetime.utcfromtimestamp(100.5)))
    self.assertEquals(100.9,
        utils.to_unix_timestamp(datetime.utcfromtimestamp(100.9)))
    self.assertEquals(-100,
        utils.to_unix_timestamp(datetime.utcfromtimestamp(-100)))
    self.assertEquals(-100.1,
        utils.to_unix_timestamp(datetime.utcfromtimestamp(-100.1)))

  def test_compressed_json_dumps(self):
    self.assertEquals('{"a":["0",1,2.5],"b":null}',
        utils.compressed_json_dumps({'a': ['0', 1, 2.5], 'b': None}))

  def test_cross_origin_json_success(self):
    webapp = MockWebApp()
    @utils.cross_origin_json
    def produce_json(self): # pylint: disable=W0613
      return {'valid': True}
    produce_json(webapp)
    self.assertEquals('{"valid":true}', webapp.response.body)
    self.assertTrue(webapp.response.headers.is_cross_origin)
    self.assertTrue(webapp.response.headers.is_json_content)

  def test_cross_origin_json_falsey_success(self):
    webapp = MockWebApp()
    @utils.cross_origin_json
    def produce_falsey_json(self): # pylint: disable=W0613
      return False
    produce_falsey_json(webapp)
    self.assertEquals('false', webapp.response.body)
    self.assertTrue(webapp.response.headers.is_cross_origin)
    self.assertTrue(webapp.response.headers.is_json_content)

  def test_cross_origin_json_fail(self):
    webapp = MockWebApp()
    @utils.cross_origin_json
    def produce_no_json(self): # pylint: disable=W0613
      pass
    produce_no_json(webapp)
    self.assertEquals('', webapp.response.body)
    self.assertTrue(webapp.response.headers.is_cross_origin)
    self.assertFalse(webapp.response.headers.is_json_content)

  def test_memcachize(self):
    c = 0
    @utils.memcachize()
    def test(a, b):
      return a + b + c
    self.assertEquals(test(a=1, b=2), 3)
    c = 1
    self.assertEquals(test(a=1, b=2), 3)
    self.assertEquals(test(a=2, b=1), 4)

  def test_memcachize_check(self):
    def check(**kwargs):
      return kwargs['use_cache']
    c = 0
    @utils.memcachize(use_cache_check=check)
    def test(a, b, use_cache): # pylint: disable=W0613
      return a + b + c
    self.assertEquals(test(a=1, b=2, use_cache=False), 3)
    c = 1
    self.assertEquals(test(a=1, b=2, use_cache=True), 4)
    c = 2
    self.assertEquals(test(a=1, b=2, use_cache=True), 4)
    self.assertEquals(test(a=2, b=1, use_cache=True), 5)
    self.assertEquals(test(a=1, b=2, use_cache=False), 5)
