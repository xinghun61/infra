# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import mock
import unittest

from google.appengine.api import urlfetch

from gae_libs.http import http_client_appengine


_Result = collections.namedtuple(
    'Result', ['content', 'status_code', 'headers'])


class HttpClientAppengineTest(unittest.TestCase):

  def testShouldLogErrorByDefault(self):
    client = http_client_appengine.HttpClientAppengine()
    self.assertFalse(client._ShouldLogError(200))
    self.assertTrue(client._ShouldLogError(404))

  def testShouldNotLogErrorForSpecificStatuses(self):
    client = http_client_appengine.HttpClientAppengine(
        no_error_logging_statuses=[404])
    self.assertFalse(client._ShouldLogError(200))
    self.assertFalse(client._ShouldLogError(404))
    self.assertTrue(client._ShouldLogError(403))

  @mock.patch.object(http_client_appengine.auth_util.Authenticator,
                     'GetHttpHeadersFor', return_value={})
  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testGet(self, mocked_fetch, mocked_GetHttpHeadersFor):
    headers = {'a': 'a'}
    timeout = 60
    client = http_client_appengine.HttpClientAppengine()
    mocked_fetch.side_effect = [
        _Result(status_code=200, content='OK', headers={})]
    status_code, content = client._Get('https://test', timeout, headers)

    self.assertEqual(200, status_code)
    self.assertEqual('OK', content)
    mocked_GetHttpHeadersFor.assert_called_once_with('https://test')

    mocked_fetch.assert_called_once_with(
        'https://test', payload=None, method=urlfetch.GET, headers=headers,
        deadline=timeout, follow_redirects=True, validate_certificate=True)

  @mock.patch.object(http_client_appengine.auth_util.Authenticator,
                     'GetHttpHeadersFor', return_value={'auth': 'key'})
  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testPost(self, mocked_fetch, mocked_GetHttpHeadersFor):
    headers = {'a': 'a'}
    timeout = 60
    client = http_client_appengine.HttpClientAppengine()
    mocked_fetch.side_effect = [
        _Result(status_code=500, content='E', headers={})]
    status_code, content = client._Post(
        'https://test', 'data', timeout, headers)

    self.assertEqual(500, status_code)
    self.assertEqual('E', content)
    mocked_GetHttpHeadersFor.assert_called_once_with('https://test')

    expected_headers = {'a': 'a', 'auth': 'key'}
    mocked_fetch.assert_called_once_with(
        'https://test', payload='data', method=urlfetch.POST,
        headers=expected_headers, deadline=timeout, follow_redirects=True,
        validate_certificate=True)

  @mock.patch.object(http_client_appengine.auth_util.Authenticator,
                     'GetHttpHeadersFor', return_value={})
  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testPut(self, mocked_fetch, mocked_GetHttpHeadersFor):
    headers = {'a': 'a'}
    timeout = 60
    client = http_client_appengine.HttpClientAppengine()
    mocked_fetch.side_effect = [
        _Result(status_code=200, content='OK', headers={'n': 'v'})]
    status_code, content = client._Put('https://test', 'data', timeout, headers)

    self.assertEqual(200, status_code)
    self.assertEqual('OK', content)
    mocked_GetHttpHeadersFor.assert_called_once_with('https://test')

    mocked_fetch.assert_called_once_with(
        'https://test', payload='data', method=urlfetch.PUT, headers=headers,
        deadline=timeout, follow_redirects=True, validate_certificate=True)
