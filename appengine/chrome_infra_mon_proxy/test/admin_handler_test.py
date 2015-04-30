# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import webtest

from testing_utils import testing
from google.appengine.api import users

import admin_handler
import common
from components import auth
from components import utils


class MockUser(object):
  def __init__(self, email=None):
    self._email = email

  def email(self):
    return self._email


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
    class MonAcqDataMock(object):
      def __init__(self, data):
        self.data = data

      def get_by_id(self, _id):
        return self.data

      def get_or_insert(self, _id):
        return self.data

    class DataMock(object):
      def __init__(self, credentials=None, url='http://',
                   scopes=None, headers=None):
        self.credentials = credentials or {}
        self.url = url
        self.scopes = scopes or ['a', 'b']
        self.headers = headers or {}
        self.updated = False

      def to_dict(self):
        return {
            'credentials': self.credentials,
            'url': self.url,
            'scopes': self.scopes,
            'headers': self.headers,
        }

      def put(self):
        self.updated = True
        logging.debug('Saving NDB data: %s', self.to_dict())

    self.mock(admin_handler.AdminDispatch, 'xsrf_token_enforce_on', [])
    self.mock(users, 'get_current_user',
              lambda: MockUser(email='jack@example.com'))
    self.mock(auth, 'is_group_member', lambda _: True) # pragma: no branch

    # Authorized GET request, no data in NDB.
    self.mock(common, 'MonAcqData', MonAcqDataMock(None))
    response = self.test_app.get('/admin/set-credentials')
    self.assertEquals(200, response.status_int)

    # Authorized GET request, data exists in NDB.
    self.mock(common, 'MonAcqData', MonAcqDataMock(DataMock()))
    response = self.test_app.get('/admin/set-credentials')
    self.assertEquals(200, response.status_int)

    # POST request with no data (for branch coverage).
    self.mock(common, 'MonAcqData', MonAcqDataMock(DataMock()))
    response = self.test_app.post('/admin/set-credentials')
    self.assertEquals(200, response.status_int)

    # Valid POST request.
    data = DataMock()
    self.mock(common, 'MonAcqData', MonAcqDataMock(data))
    params = collections.OrderedDict([
        ('url', 'https://new.url'),
        ('credentials', '{"client_id": "john@doe"}'),
        ('scopes', 'foo \n bar\t'),
    ])
    response = self.test_app.post('/admin/set-credentials', params)
    self.assertEquals(200, response.status_int)
    self.assertTrue(data.updated)
    self.assertEquals(data.scopes, ['foo', 'bar'])

    # Invalid POST request.
    data = DataMock()
    self.mock(common, 'MonAcqData', MonAcqDataMock(data))
    params = collections.OrderedDict([
        ('credentials', '{"client_id": '), # Bad JSON.
    ])
    response = self.test_app.post('/admin/set-credentials', params)
    self.assertEquals(200, response.status_int)
    self.assertFalse(data.updated)
