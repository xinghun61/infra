# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import random
import webtest

import oauth2client.client
import googleapiclient.http
from google.appengine.api import app_identity
from testing_utils import testing

import common
import vm_module


class VMModuleTest(testing.AppengineTestCase):

  def test_get_config_data(self):
    self.assertIsNone(vm_module._get_config_data())

    data = common.ConfigData(id=common.CONFIG_DATA_KEY)
    data.put()
    self.assertEquals(vm_module._get_config_data(), data)

  def test_get_credentials(self):
    class CredentialsMock(object):
      def __init__(self, **kwargs):
        pass
    self.mock(oauth2client.client, 'SignedJwtAssertionCredentials',
              CredentialsMock)
    creds = common.Credentials()
    scopes = ['this', 'that']
    self.assertIsNone(vm_module._get_credentials(creds, scopes))

    creds = common.Credentials(
        client_email='we@you.me',
        client_id='agent007',
        private_key='deadbeafyoudneverguess',
        private_key_id='!@#$%')
    self.assertIsNotNone(vm_module._get_credentials(creds, scopes))


class VMHandlerTest(testing.AppengineTestCase):

  @property
  def app_module(self):
    return vm_module.app

  def test_get(self):
    with self.assertRaises(webtest.AppError) as cm:
      self.test_app.get('/vm1/1.2.3.4')
    logging.info('exception = %s', cm.exception)
    self.assertIn('405', str(cm.exception))

  def test_post(self):
    # Authenticated production server.
    self.mock(os, 'environ', {'SERVER_SOFTWARE': 'GAE production server'})
    headers = {'X-Appengine-Inbound-Appid': 'my-app-id'}

    # Authentication fails.
    self.mock(app_identity, 'get_application_id', lambda: 'bad-app-id')
    with self.assertRaises(webtest.AppError) as cm:
      self.test_app.post('/vm1/5.6.7.8', '', headers=headers)
    logging.info('exception = %s', cm.exception)
    self.assertIn('403', str(cm.exception))

    # Authentication succeeds.
    self.mock(app_identity, 'get_application_id', lambda: 'my-app-id')

    # No data is configured.
    self.mock(vm_module, '_get_config_data', lambda: None)
    with self.assertRaises(webtest.AppError) as cm:
      self.test_app.post('/vm1/1.3.6.9', '', headers=headers)
    logging.info('exception = %s', cm.exception)
    self.assertIn('500', str(cm.exception))

    # Data is correct. url2 is 20%, and is selected.
    creds = common.Credentials(
        client_email='we@you.me',
        client_id='agent007',
        private_key='deadbeafyoudneverguess',
        private_key_id='!@#$%')

    class CredentialsMock(object):
      def __init__(self, **kwargs):
        pass

      def authorize(self, x):
        return x

    self.mock(oauth2client.client, 'SignedJwtAssertionCredentials',
              CredentialsMock)
    data = common.ConfigData(
        primary_endpoint=common.Endpoint(url='foo://', scopes=['this', 'that']),
        secondary_endpoint=common.Endpoint(url='bar://', credentials=creds),
        secondary_endpoint_load=20,
        id=common.CONFIG_DATA_KEY)
    self.mock(vm_module, '_get_config_data', lambda: data)
    self.mock(random, 'uniform', lambda _a, _b: 10.0)

    class ResponseMock(dict):
      def __init__(self, status, reason):
        self.status = status
        self.reason = reason

    # Production server, unsuccessful request.
    def execute_mock_bad(self):
      self.postproc(ResponseMock(404, 'Not OK'), 'content')
    self.mock(googleapiclient.http.HttpRequest, 'execute', execute_mock_bad)

    response = self.test_app.post('/vm1/2620:0:1000', '', headers=headers)
    logging.info('response = %s', response)
    self.assertEquals(200, response.status_int)

    # Production server, secondary URL, successful request.
    def execute_mock_good(self):
      self.postproc(ResponseMock(200, 'OK'), 'content')
    self.mock(googleapiclient.http.HttpRequest, 'execute', execute_mock_good)

    response = self.test_app.post('/vm1/10.9.8.7', '', headers=headers)
    logging.info('response = %s', response)
    self.assertEquals(200, response.status_int)

    # Same for the primary URL, for branch coverage.
    self.mock(random, 'uniform', lambda _a, _b: 21.0)
    response = self.test_app.post('/vm1/10.9.8.7', '', headers=headers)
    logging.info('response = %s', response)
    self.assertEquals(200, response.status_int)

    # Dev appserver (for branch coverage).
    self.mock(os, 'environ', {'SERVER_SOFTWARE': 'Development server'})
    response = self.test_app.post('/vm1/25.36.47.79', '', headers=headers)
    logging.info('response = %s', response)
    self.assertEquals(200, response.status_int)
