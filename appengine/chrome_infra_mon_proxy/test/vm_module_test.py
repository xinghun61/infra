# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import random
import urllib
import webtest

import mock
from google.appengine.api import app_identity
from testing_utils import testing

import common
import vm_module


class VMHandlerTest(testing.AppengineTestCase):

  @property
  def app_module(self):
    return vm_module.app

  def test_get(self):
    with self.assertRaises(webtest.AppError) as cm:
      self.test_app.get('/vm1/1.2.3.4')
    logging.info('exception = %s', cm.exception)
    self.assertIn('405', str(cm.exception))

  @mock.patch('urllib2.Request', autospec=True)
  @mock.patch('urllib2.urlopen', autospec=True)
  def test_post(self, _urlopen_mock, _request_mock):
    # Authenticated production server.
    self.mock(os, 'environ', {'SERVER_SOFTWARE': 'GAE production server'})
    gae_headers = {'X-Appengine-Inbound-Appid': 'my-app-id'}

    # Authentication fails.
    self.mock(app_identity, 'get_application_id', lambda: 'bad-app-id')
    with self.assertRaises(webtest.AppError) as cm:
      self.test_app.post('/vm1', '', headers=gae_headers)
    logging.info('exception = %s', cm.exception)
    self.assertIn('403', str(cm.exception))

    # Authentication succeeds.
    self.mock(app_identity, 'get_application_id', lambda: 'my-app-id')

    url = 'https://test-endpoint'
    headers = {
        'Content-Type': 'application/x-protobuf',
        'Authorization': 'Bearer super-secret-test-token',
    }
    stripped_headers = {
        'Host': 'test.host',
        'User-Agent': '007',
        'X-Appengine-Special-Header': 'remove me',
    }
    post_headers = {}
    post_headers.update(headers)
    post_headers.update(gae_headers)
    post_headers.update(stripped_headers)
    payload = 'test payload'

    # No Endpoint-Url header is specified.
    with self.assertRaises(webtest.AppError) as cm:
      self.test_app.post('/vm1', '', headers=gae_headers)
    logging.info('exception = %s', cm.exception)
    self.assertIn('500', str(cm.exception))

    # All is well now.
    post_headers[common.ENDPOINT_URL_HEADER] = url
    self.test_app.post('/vm1', payload, headers=post_headers)
    self.assertEqual(_urlopen_mock.call_args[0][0], _request_mock.return_value)
    self.assertEqual(_request_mock.call_args[0][0], url)
    self.assertEqual(_request_mock.call_args[0][1], payload)
    self.assertEqual(_request_mock.call_args[0][2], headers)

    # Dev appserver (for branch coverage).
    self.mock(os, 'environ', {'SERVER_SOFTWARE': 'Development server'})
    self.test_app.post('/vm1', payload, headers=post_headers)
    self.assertEqual(_urlopen_mock.call_args[0][0], _request_mock.return_value)
    self.assertEqual(_request_mock.call_args[0][0], url)
    self.assertEqual(_request_mock.call_args[0][1], payload)
    self.assertEqual(_request_mock.call_args[0][2], headers)
