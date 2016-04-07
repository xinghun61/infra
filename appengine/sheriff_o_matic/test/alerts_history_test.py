# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import alerts
import alerts_history
import contextlib
import datetime
import json
import string
import unittest

import cloudstorage as gcs

from testing_utils import testing


class AlertsHistoryTest(testing.AppengineTestCase):
  app_module = alerts_history.app

  def test_alerts_jsons_are_retrieved_from_history(self):
    test_alert = {'alerts': ['hello', 'world', '1']}
    alerts.AlertsJSON(json=json.dumps(test_alert), type='alerts').put()
    response = self.test_app.get('/alerts-history')
    self.assertEqual(response.status_int, 200)
    self.assertEqual(response.content_type, 'application/json')
    parsed_json = json.loads(response.normal_body)
    self.assertEqual(len(parsed_json['history']), 1)

    entry_id = parsed_json['history'][0]
    response = self.test_app.get('/alerts-history/%s' % entry_id)
    self.assertEqual(response.status_int, 200)
    self.assertEqual(response.content_type, 'application/json')
    parsed_json = json.loads(response.normal_body)
    self.assertEqual(parsed_json['alerts'], test_alert['alerts'])

  def test_alerts_json_in_gcs(self):
    test_alert = {'alerts': ['hello', 'world', '1']}
    filename = datetime.datetime.utcnow().strftime("%Y/%m/%d/%H.%M.%S.%f")
    with contextlib.closing(gcs.open(
        "/app_default_bucket/history/alerts/" + filename, 'w')) as f:
      f.write(json.dumps(test_alert))

    itm = alerts.AlertsJSON(type='alerts', gcs_filename=filename).put()

    response = self.test_app.get('/alerts-history/%s' % itm.id())
    self.assertEqual(response.status_int, 200)
    self.assertEqual(response.content_type, 'application/json')
    parsed_json = json.loads(response.normal_body)
    self.assertEqual(parsed_json['alerts'], test_alert['alerts'])

  def test_provides_login_url(self):
    response = self.test_app.get('/alerts-history')
    self.assertIn('login-url', response)

  def test_invalid_keys_return_400(self):
    response = self.test_app.get('/alerts-history/kjhg$%T',
                                expect_errors=True)
    self.assertEqual(response.status_int, 400)

  def test_non_existing_keys_return_404(self):
    response = self.test_app.get('/alerts-history/5348024557502464',
                                expect_errors=True)
    self.assertEqual(response.status_int, 404)

  def test_internal_alerts_can_only_retrieved_by_internal_users(self):
    test_alert = {'alerts': ['hello', 'world', '1']}
    internal_alert = alerts.AlertsJSON(json=json.dumps(test_alert),
                                       type='internal-alerts')
    internal_alert_key = internal_alert.put().integer_id()

    # No signed-in user.
    self.test_app.get('/alerts-history/%s' % internal_alert_key,
                      expect_errors=True, status=404)

    # Non-internal user.
    self.testbed.setup_env(USER_EMAIL='test@example.com', USER_ID='1',
                           USER_IS_ADMIN='1', overwrite=True)
    self.test_app.get('/alerts-history/%s' % internal_alert_key,
                      expect_errors=True, status=404)

  def test_lists_internal_alerts_to_internal_users_only(self):
    test_alert = {'alerts': ['hello', 'world', '1']}
    alerts.AlertsJSON(json=json.dumps(test_alert),
                      type='internal-alerts').put()

    # No signed-in user.
    response = self.test_app.get('/alerts-history')
    self.assertEqual(response.status_int, 200)
    self.assertEqual(response.content_type, 'application/json')
    response_json = json.loads(response.normal_body)
    self.assertEqual(len(response_json['history']), 0)

    # Non-internal user.
    self.testbed.setup_env(USER_EMAIL='test@example.com', USER_ID='1',
                           USER_IS_ADMIN='1', overwrite=True)
    response = self.test_app.get('/alerts-history')
    self.assertEqual(response.status_int, 200)
    self.assertEqual(response.content_type, 'application/json')
    response_json = json.loads(response.normal_body)
    self.assertEqual(len(response_json['history']), 0)

    # Internal user.
    self.testbed.setup_env(USER_EMAIL='test@google.com', USER_ID='2',
                           USER_IS_ADMIN='1', overwrite=True)
    response = self.test_app.get('/alerts-history')
    self.assertEqual(response.status_int, 200)
    self.assertEqual(response.content_type, 'application/json')
    response_json = json.loads(response.normal_body)
    self.assertEqual(len(response_json['history']), 1)

  def test_returned_alerts_from_history_are_paged(self):
    for i in range(20):
      test_alert = {'alerts': ['hello', 'world', i]}
      alerts.AlertsJSON(json=json.dumps(test_alert), type='alerts').put()

    response = self.test_app.get('/alerts-history?limit=15')
    self.assertEqual(len(response.json['history']), 15)
    self.assertEqual(response.json['has_more'], True)

    url = '/alerts-history?limit=15&cursor=%s' % response.json['cursor']
    response = self.test_app.get(url)
    self.assertEqual(response.status_int, 200)
    self.assertEqual(response.content_type, 'application/json')
    response_json = json.loads(response.normal_body)
    self.assertEqual(len(response_json['history']), 5)
    self.assertEqual(response_json['has_more'], False)

