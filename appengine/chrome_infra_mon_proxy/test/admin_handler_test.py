# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import logging
import webtest

from testing_utils import testing
from google.appengine.api import users
from google.appengine.ext import ndb

import admin_handler
import common
from components import auth
from components import utils


class MockUser(object):
  def __init__(self, email=None):
    self._email = email

  def email(self):
    return self._email

  def user_id(self):
    return '1234567'


class AdminTest(testing.AppengineTestCase):

  @property
  def app_module(self):
    return admin_handler.create_app()

  def setUp(self):
    super(AdminTest, self).setUp()
    self.mock(utils, 'is_local_dev_server', lambda: True)

  def test_create_app(self):
    """Branch coverage for production server."""
    self.mock(utils, 'is_local_dev_server', lambda: False)
    admin_handler.create_app()

  def test_update_config(self):
    """Test error condition for coverage."""
    with self.assertRaises(Exception):
      admin_handler.updateConfig(common.ConfigData(), 'bad field', 'value')

  def test_admin_page(self):
    # Authorized GET request.
    self.mock(admin_handler.AdminDispatch, 'xsrf_token_enforce_on', [])
    # Note: auth.autologin explicitly checks for
    # users.get_current_user(), and not auth.get_current_identity().
    self.mock(users, 'get_current_user',
              lambda: MockUser(email='jack@example.com'))
    self.mock(auth, 'is_group_member', lambda _: True) # pragma: no branch
    response = self.test_app.get('/admin/')
    logging.info('response = %s', response)
    self.assertEquals(200, response.status_int)

    # Authorized POST request: 403 (POST not allowed on /admin/).
    with self.assertRaises(webtest.AppError) as cm:
      self.test_app.post('/admin/')
    logging.info('exception = %s', cm.exception)
    self.assertIn('403', str(cm.exception))

  def test_set_credentials(self):
    self.mock(admin_handler.AdminDispatch, 'xsrf_token_enforce_on', [])
    self.mock(users, 'get_current_user',
              lambda: MockUser(email='jack@example.com'))
    self.mock(auth, 'is_group_member', lambda _: True) # pragma: no branch

    # Authorized GET request, no data in NDB.
    response = self.test_app.get('/admin/set-credentials')
    self.assertEquals(200, response.status_int)

    # Authorized GET request, data exists in NDB.
    common.ConfigData().get_or_insert(common.CONFIG_DATA_KEY)
    response = self.test_app.get('/admin/set-credentials')
    self.assertEquals(200, response.status_int)

    # POST request with no data (for branch coverage).
    response = self.test_app.post('/admin/set-credentials')
    self.assertEquals(200, response.status_int)

    # Valid POST request.
    creds = common.Credentials(
        client_email='joe@don', private_key='secret', private_key_id='blah')
    creds2 = common.Credentials(
        client_email='jane@doe', private_key='asfd', private_key_id='foo')
    params = collections.OrderedDict([
        ('primary_url', 'https://new.url'),
        ('secondary_url', 'https://alt.url'),
        ('primary_credentials', json.dumps(creds.to_dict())),
        ('secondary_credentials', json.dumps(creds2.to_dict())),
        ('secondary_endpoint_load', 30),
        ('primary_scopes', 'foo \n bar\t'),
        ('secondary_scopes', 'bar \n baz'),
    ])
    # Clean up the data, start fresh.
    ndb.Key('ConfigData', common.CONFIG_DATA_KEY).delete()
    response = self.test_app.post('/admin/set-credentials', params)
    self.assertEquals(200, response.status_int)
    data = common.ConfigData.get_by_id(common.CONFIG_DATA_KEY)
    self.assertEquals(data.primary_endpoint.url, params['primary_url'])

    # TODO(sergeyberezin): bug in testing framework: multiple
    # instances of the same StructuredProperty collapse to the same
    # value, but it works great in production. So, we cannot unittest
    # that credentials are set correctly.

    # self.assertEquals(data.primary_endpoint.credentials, creds)
    # self.assertEquals(data.secondary_endpoint.credentials, creds2)

    self.assertEquals(data.secondary_endpoint.url, params['secondary_url'])
    self.assertEquals(data.secondary_endpoint_load,
                      params['secondary_endpoint_load'])
    self.assertEquals(data.primary_endpoint.scopes, ['foo', 'bar'])

    # Invalid POST request: succeeds, but data is not updated.
    data.key.delete()
    params = collections.OrderedDict([
        ('primary_credentials', '{"client_id": '), # Bad JSON.
    ])
    response = self.test_app.post('/admin/set-credentials', params)
    self.assertEquals(200, response.status_int)
    data = common.ConfigData.get_by_id(common.CONFIG_DATA_KEY)
    self.assertEquals(data.primary_endpoint.credentials.client_id, '')

    # Incomplete JSON in POST request: succeeds, but data is not updated.
    data.key.delete()
    params = collections.OrderedDict([
        ('primary_credentials', '{"client_id": "foo"}'),
    ])
    response = self.test_app.post('/admin/set-credentials', params)
    self.assertEquals(200, response.status_int)
    data = common.ConfigData.get_by_id(common.CONFIG_DATA_KEY)
    self.assertEquals(data.primary_endpoint.credentials.client_id, '')

  def test_set_traffic(self):
    self.mock(admin_handler.AdminDispatch, 'xsrf_token_enforce_on', [])
    self.mock(users, 'get_current_user',
              lambda: MockUser(email='jack@example.com'))
    self.mock(auth, 'is_group_member', lambda _: True) # pragma: no branch

    # GET request.
    response = self.test_app.get('/admin/set-traffic')
    self.assertEquals(200, response.status_int)

    # POST request with no data (for branch coverage).
    response = self.test_app.post('/admin/set-traffic')
    self.assertEquals(200, response.status_int)

    # POST request with data.
    params = collections.OrderedDict([
        ('vm1', 100), ('vm2', 40), ('vm3', 80),
        ('secondary_endpoint_load', 20)
    ])
    response = self.test_app.post('/admin/set-traffic', params)
    self.assertEquals(200, response.status_int)
    data = common.TrafficSplit.get_by_id(common.TRAFFIC_SPLIT_KEY)
    config = common.ConfigData.get_by_id(common.CONFIG_DATA_KEY)
    self.assertEquals(data.vm1, params['vm1'])
    self.assertEquals(data.vm2, params['vm2'])
    self.assertEquals(data.vm3, params['vm3'])
    self.assertEquals(config.secondary_endpoint_load,
                      params['secondary_endpoint_load'])

    # Invalid POST request: succeeds, but data is not updated (stays default).
    data.key.delete()
    params = collections.OrderedDict([
        ('vm1', 'b'),
        ('secondary_endpoint_load', 'z')
    ])
    response = self.test_app.post('/admin/set-traffic', params)
    self.assertEquals(200, response.status_int)
    data = common.TrafficSplit.get_by_id(common.TRAFFIC_SPLIT_KEY)
    self.assertEquals(data.vm1, 100)
