# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import alerts
import internal_alerts
import json
import random
import string
import unittest
import webtest

from google.appengine.api import memcache
from google.appengine.ext import testbed

from testing_utils import testing
from components import auth
from components import auth_testing


class InternalAlertsTest(testing.AppengineTestCase):
  app_module = internal_alerts.app

  def check_json_headers(self, res):
    self.assertEqual(res.content_type, 'application/json')
    # This is necessary for cross-site tools to retrieve internal alerts.
    self.assertEqual(res.headers['access-control-allow-origin'], '*')

  def test_get_no_data_cached(self):
    auth_testing.mock_get_current_identity(self)
    self.mock(auth, 'is_group_member', lambda group: True)

    res = self.test_app.get('/internal-alerts')
    self.check_json_headers(res)
    self.assertEqual(res.body, '{}')

  def test_happy_path(self):
    auth_testing.mock_get_current_identity(self)
    self.mock(auth, 'is_group_member', lambda group: True)

    # Set it.
    self.test_app.post_json('/internal-alerts', {"alerts": ["hello", "world"]})

    def happy_path():
      # Get it.
      res = self.test_app.get('/internal-alerts')
      self.check_json_headers(res)
      data = json.loads(res.body)

      # The server should have stuck a 'date' on there.
      self.assertTrue('date' in data)
      self.assertEqual(type(data['date']), int)

      self.assertEqual(data['alerts'], ['hello', 'world'])

    happy_path()

    memcache.Client().flush_all()

    happy_path()

  def test_post_invalid_data_not_reflected(self):
    auth_testing.mock_get_current_identity(self)
    self.mock(auth, 'is_group_member', lambda group: True)

    self.test_app.post(
        '/internal-alerts', '[{"this is not valid JSON', status=400)
    res = self.test_app.get('/internal-alerts')
    self.assertEqual(res.body, '{}')

  def test_post_invalid_data_does_not_overwrite_valid_data(self):
    auth_testing.mock_get_current_identity(self)
    self.mock(auth, 'is_group_member', lambda group: True)

    # Populate the cache with something valid
    self.test_app.post_json('/internal-alerts', {"alerts": "everything is OK"})
    self.test_app.post('/internal-alerts', {'content': 'woozlwuzl'},
                      status=400)

    res = self.test_app.get('/internal-alerts')
    self.check_json_headers(res)
    data = json.loads(res.body)
    self.assertEqual(data['alerts'], 'everything is OK')

  def test_internal_alerts_stored_in_history_have_correct_type(self):
    test_alerts1 = {'alerts': ['hello', 'world', '1']}
    test_alerts2 = {'alerts': ['hello', 'world', '2']}
    self.test_app.post_json('/internal-alerts', test_alerts1)
    self.test_app.post_json('/internal-alerts', test_alerts2)

    alerts_query = alerts.AlertsJSON.query().order(alerts.AlertsJSON.date)
    stored_alerts = alerts_query.fetch(limit=3)
    self.assertEqual(2, len(stored_alerts))
    self.assertEqual(stored_alerts[0].type, 'internal-alerts')
    self.assertEqual(stored_alerts[1].type, 'internal-alerts')

  def test_internal_alerts_same_as_last_alerts_are_added_to_history(self):
    test_alerts = {'alerts': ['hello', 'world']}
    alerts.AlertsJSON(json=json.dumps(test_alerts), type='alerts').put()

    self.test_app.post_json('/internal-alerts', test_alerts)
    alerts_query = alerts.AlertsJSON.query()
    self.assertEqual(2, alerts_query.count(limit=3))

  def test_large_number_of_internal_alerts(self):
    auth_testing.mock_get_current_identity(self)
    self.mock(auth, 'is_group_member', lambda group: True)

    put_internal_alerts = {'alerts': ['hi', 'there']}
    self.mock(alerts.AlertsHandler, 'can_put_in_datastore', lambda *args: False)

    self.test_app.post_json('/internal-alerts', put_internal_alerts)

    res = self.test_app.get('/internal-alerts')
    got_internal_alerts = json.loads(res.body)
    self.assertEquals(got_internal_alerts['alerts'],
                      put_internal_alerts['alerts'])

  def test_alerts_too_big_for_memcache(self):
    auth_testing.mock_get_current_identity(self)
    self.mock(auth, 'is_group_member', lambda group: True)

    big_alerts = {'alerts': ['hi', 'there']}
    self.mock(alerts.AlertsHandler, 'can_put_in_datastore', lambda *args: False)

    self.test_app.post_json('/internal-alerts', big_alerts)
    res = self.test_app.get('/internal-alerts')
    got_alerts = json.loads(res.body)
    self.assertEquals(got_alerts['alerts'], big_alerts['alerts'])
    alerts_type = internal_alerts.InternalAlertsHandler.ALERT_TYPE
    self.assertEquals(memcache.get(alerts_type), None)

  def test_no_user(self):
    # Get it.
    res = self.test_app.get('/internal-alerts')
    self.check_json_headers(res)
    data = json.loads(res.body)

    # The server should have stuck a 'date' on there.
    self.assertTrue('date' in data)
    self.assertEqual(type(data['date']), int)

    self.assertTrue('redirect-url' in data)
    self.assertEqual(type(data['redirect-url']), unicode)

  def test_invalid_user(self):
    auth_testing.mock_get_current_identity(self)
    self.mock(auth, 'is_group_member', lambda group: False)

    self.test_app.get('/internal-alerts', status=403)

