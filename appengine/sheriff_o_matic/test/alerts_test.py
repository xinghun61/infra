# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import alerts
import json
import random
import string
import unittest

from google.appengine.api import memcache

from testing_utils import testing


class AlertsTest(testing.AppengineTestCase):
  app_module = alerts.app

  def check_json_headers(self, res):
    self.assertEqual(res.content_type, 'application/json')
    # This is necessary for cross-site tools to retrieve alerts
    self.assertEqual(res.headers['access-control-allow-origin'], '*')

  def test_get_no_data_cached(self):
    res = self.test_app.get('/alerts')
    self.check_json_headers(res)
    self.assertEqual(res.body, '{}')

  def test_happy_path(self):
    # Set it.
    data = {"alerts": ["hello", "world"]}
    self.test_app.post_json('/alerts', data)

    def happy_path():
      # Get it.
      res = self.test_app.get('/alerts')
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
    self.test_app.post('/alerts', '[{"this is not valid JSON', status=400)
    res = self.test_app.get('/alerts')
    self.assertEqual(res.body, '{}')

  def test_post_invalid_data_does_not_overwrite_valid_data(self):
    # Populate the cache with something valid
    data = {"alerts": "everything is OK"}
    self.test_app.post_json('/alerts', data)
    self.test_app.post('/alerts', 'woozlwuzl', status=400)

    res = self.test_app.get('/alerts')
    self.check_json_headers(res)
    data = json.loads(res.body)
    self.assertEqual(data['alerts'], 'everything is OK')

  def test_alerts_jsons_are_stored_in_history(self):
    test_alerts1 = {'alerts': ['hello', 'world', '1']}
    test_alerts2 = {'alerts': ['hello', 'world', '2']}
    self.test_app.post_json('/alerts', test_alerts1)
    self.test_app.post_json('/alerts', test_alerts2)
    alerts_query = alerts.AlertsJSON.query().order(alerts.AlertsJSON.date)
    stored_alerts = alerts_query.fetch(limit=3)
    self.assertEqual(2, len(stored_alerts))
    self.assertEqual(stored_alerts[0].type, 'alerts')
    self.assertEqual(stored_alerts[1].type, 'alerts')
    stored_alerts1 = json.loads(stored_alerts[0].json)
    stored_alerts2 = json.loads(stored_alerts[1].json)
    self.assertEqual(test_alerts1['alerts'], stored_alerts1['alerts'])
    self.assertEqual(test_alerts2['alerts'], stored_alerts2['alerts'])
    self.assertTrue('date' in stored_alerts1)
    self.assertTrue('date' in stored_alerts2)
    self.assertEqual(type(stored_alerts1['date']), int)
    self.assertEqual(type(stored_alerts2['date']), int)

  def test_repeating_alerts_are_not_stored_to_history(self):
    test_alerts = {'alerts': ['hello', 'world']}
    self.test_app.post_json('/alerts', test_alerts)

    test_alerts['last_builder_info'] = {'some': 'info'}
    self.test_app.post_json('/alerts', test_alerts)
    stored_alerts = alerts.AlertsJSON.query().fetch(limit=2)

    self.assertEqual(1, len(stored_alerts))


  def test_large_number_of_alerts(self):
    put_alerts = {'alerts': ['hi', 'there']}
    self.mock(alerts.AlertsHandler, 'can_put_in_datastore', lambda *args: False)

    self.test_app.post_json('/alerts', put_alerts)

    res = self.test_app.get('/alerts')
    got_alerts = json.loads(res.body)
    self.assertEquals(got_alerts['alerts'], put_alerts['alerts'])

  def test_alerts_too_big_for_memcache(self):
    big_alerts = {'alerts': ['hi', 'there']}
    self.mock(alerts.AlertsHandler, 'can_put_in_datastore', lambda *args: False)

    self.test_app.post_json('/alerts', big_alerts)
    res = self.test_app.get('/alerts')
    got_alerts = json.loads(res.body)
    self.assertEquals(got_alerts['alerts'], big_alerts['alerts'])
    self.assertEquals(memcache.get(alerts.AlertsHandler.ALERT_TYPE), None)

  def test_update_alerts_when_last_was_stored_in_gcs(self):
    alerts_1 = {'alerts': ['hi', 'there']}
    self.mock(alerts.AlertsHandler, 'can_put_in_datastore', lambda *args: False)
    self.test_app.post_json('/alerts', alerts_1)

    test_alerts2 = {'alerts': ['hello', 'world', '1']}
    self.mock(alerts.AlertsHandler, 'can_put_in_datastore', lambda *args: True)
    self.test_app.post_json('/alerts', test_alerts2)
    alerts_query = alerts.AlertsJSON.query().order(alerts.AlertsJSON.date)
    stored_alerts = alerts_query.fetch(limit=3)
    print stored_alerts
    self.assertEqual(2, len(stored_alerts))
    self.assertEqual(stored_alerts[0].type, 'alerts')
    self.assertEqual(stored_alerts[1].type, 'alerts')
    self.assertTrue(stored_alerts[0].gcs_filename)
    stored_alerts2 = json.loads(stored_alerts[1].json)
    self.assertEqual(test_alerts2['alerts'], stored_alerts2['alerts'])
    self.assertTrue('date' in stored_alerts2)
    self.assertEqual(type(stored_alerts2['date']), int)

