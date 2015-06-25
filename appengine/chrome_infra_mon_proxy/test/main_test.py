# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import os
import random
import urllib2
import webtest

import mock

from google.appengine.ext import ndb
from google.appengine.api import users
from testing_utils import testing

import common
import main
from components import auth
from components import utils


class MonacqHandlerTest(testing.AppengineTestCase):

  @property
  def app_module(self):
    return main.create_app()

  def setUp(self):
    super(MonacqHandlerTest, self).setUp()
    # Disable auth module checks.
    self.mock(users, 'get_current_user',
              lambda: users.User('test@user.com', 'auth_domain'))
    self.mock(main.MonacqHandler, 'xsrf_token_enforce_on', [])
    self.mock(auth, 'is_group_member', lambda _: True) # pragma: no branch
    self.mock(auth, 'bootstrap_group', lambda *_: None)
    # Need this to prevent payload from being mangled.
    self.headers = {'Content-Type': 'application/x-protobuf'}


  def test_biased_choice(self):
    items = collections.OrderedDict([('a', 100), ('b', 25), ('c', 75)])
    self.mock(random, 'uniform', lambda a, b: 0.0 * (b - a))
    self.assertEquals('a', main.LoadBalancer.biased_choice(items))
    self.mock(random, 'uniform', lambda a, b: 0.4999 * (b - a))
    self.assertEquals('a', main.LoadBalancer.biased_choice(items))
    self.mock(random, 'uniform', lambda a, b: 0.5 * (b - a))
    self.assertEquals('b', main.LoadBalancer.biased_choice(items))
    self.mock(random, 'uniform', lambda a, b: 0.62499 * (b - a))
    self.assertEquals('b', main.LoadBalancer.biased_choice(items))
    self.mock(random, 'uniform', lambda a, b: 0.625 * (b - a))
    self.assertEquals('c', main.LoadBalancer.biased_choice(items))
    self.mock(random, 'uniform', lambda a, b: 1.0 * (b - a))
    self.assertEquals('c', main.LoadBalancer.biased_choice(items))
    self.assertIsNone(main.LoadBalancer.biased_choice({}))

  def test_get(self):
    # GET request is not allowed.
    with self.assertRaises(webtest.AppError) as cm:
      self.test_app.get('/monacq')
    logging.info('exception = %s', cm.exception)
    self.assertIn('405', str(cm.exception))

  @classmethod
  def populate_config(cls):
    creds = common.Credentials(
        client_email='we@you.me',
        client_id='agent007',
        private_key='deadbeafyoudneverguess',
        private_key_id='!@#$%')

    data = common.ConfigData(
        primary_endpoint=common.Endpoint(url='foo://', scopes=['this', 'that']),
        secondary_endpoint=common.Endpoint(url='bar://', credentials=creds),
        secondary_endpoint_load=20,
        id=common.CONFIG_DATA_KEY)
    data.put()

  @classmethod
  def erase_config(cls):
    ndb.Key('ConfigData', common.CONFIG_DATA_KEY).delete()

  @classmethod
  def get_config(cls):
    return ndb.Key('ConfigData', common.CONFIG_DATA_KEY).get()

  @mock.patch('components.net.request', spec=True)
  def test_no_config_fail(self, _request_mock):
    self.erase_config()
    with self.assertRaises(webtest.AppError) as cm:
      self.test_app.post('/monacq')
    logging.info('exception = %s', cm.exception)
    self.assertIn('500', str(cm.exception))

  @mock.patch('components.net.request', spec=True)
  def test_secondary_endpoint_dev_appserver(self, _request_mock):
    self.populate_config()
    # Secondary url is at 20%, make it selected.
    self.mock(random, 'uniform', lambda _a, _b: 10.0)
    self.mock(utils, 'is_local_dev_server', lambda: True)
    payload = 'dev-2-deadbeafdata'

    self.test_app.post('/monacq', payload, headers=self.headers)
    self.assertEqual(_request_mock.call_args[1]['payload'], payload)
    self.assertEqual(
        _request_mock.call_args[1]['headers'].get(common.ENDPOINT_URL_HEADER),
        self.get_config().secondary_endpoint.url)
    self.assertEqual(
        _request_mock.call_args[1]['headers'].get('Content-Type'),
        'application/x-protobuf')

  @mock.patch('components.net.request', spec=True)
  def test_secondary_endpoint_prod(self, _request_mock):
    self.populate_config()
    self.mock(random, 'uniform', lambda _a, _b: 10.0)
    self.mock(utils, 'is_local_dev_server', lambda: False)

    payload = 'prod-2-deadbeafdata'
    self.test_app.post('/monacq', payload, headers=self.headers)
    self.assertEqual(_request_mock.call_args[1]['payload'], payload)
    self.assertEqual(
        _request_mock.call_args[1]['headers'].get(common.ENDPOINT_URL_HEADER),
        self.get_config().secondary_endpoint.url)
    self.assertEqual(
        _request_mock.call_args[1]['headers'].get('Content-Type'),
        'application/x-protobuf')

  @mock.patch('components.net.request', spec=True)
  def test_primary_endpoint_prod(self, _request_mock):
    self.populate_config()
    self.mock(utils, 'is_local_dev_server', lambda: False)
    self.mock(random, 'uniform', lambda _a, _b: 21.0)

    payload = 'prod-1-deadbeafdata'
    self.test_app.post('/monacq', payload, headers=self.headers)
    self.assertEqual(_request_mock.call_args[1]['payload'], payload)
    self.assertEqual(
        _request_mock.call_args[1]['headers'].get(common.ENDPOINT_URL_HEADER),
        self.get_config().primary_endpoint.url)


class MainHandlerTest(testing.AppengineTestCase):

  @property
  def app_module(self):
    return main.create_app()

  def setUp(self):
    super(MainHandlerTest, self).setUp()
    self.mock(utils, 'is_local_dev_server', lambda: True)

  def test_get(self):
    response = self.test_app.get('/')
    logging.info('response = %s', response)
    self.assertEquals(200, response.status_int)

  def test_create_app(self):
    """Branch coverage for production server."""
    self.mock(utils, 'is_local_dev_server', lambda: False)
    main.create_app()
