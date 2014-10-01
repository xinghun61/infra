# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from appengine_module.heartbeat import app
from appengine_module.heartbeat import models
from appengine_module.testing_utils import testing


class CronWorkerTest(testing.AppengineTestCase):
  """Unit tests for app.CronWorker."""
  app_module = app.app

  def test_no_configs(self):
    """Tests that CronWorker send no alerts when there are no configs."""
    self.test_app.get('/cron')
    self.assertFalse(models.Alert.query().get())

  def test_no_heartbeat(self):
    """Tests that CronWorker sends an alert when there are no heartbeats."""
    # Set something in the config, but don't set any heartbeats.
    models.Config(
      sender='test@example.com',
      timeout=1,
      watchlist=['smut@google.com'],
    ).put()

    self.test_app.get('/cron')

    # Since there were no heartbeats, expect an alert to be sent.
    alert = models.Alert.query().get()
    self.assertTrue(alert)
    self.assertEquals('test@example.com', alert.sender)
    self.assertEquals(1, alert.total)

  def test_outdated_heartbeat(self):
    """Tests that CronWorker sends alerts when there are outdated heartbeats."""
    # Set some stuff in the config.
    models.Config(
      sender='test+1@example.com',
      timeout=5,
      watchlist=['smut@example.com'],
    ).put()
    models.Config(
      sender='test+2@example.com',
      timeout=10,
      watchlist=['smut@google.com'],
    ).put()
    models.Config(
      sender='test+3@example.com',
      timeout=20,
      watchlist=['smut@google.com'],
    ).put()

    # Set some received heartbeats.
    # For this test:
    # test+1 not received at all
    # test+2 not received in time
    # test+3 received in time
    models.MostRecentHeartbeat(
      id='test+2@example.com-latest',
      sender='test+2@example.com',
      timestamp=datetime.datetime.now() - datetime.timedelta(minutes=15)
    ).put()

    models.MostRecentHeartbeat(
      id='test+3@example.com-latest',
      sender='test+3@example.com',
      timestamp=datetime.datetime.now() - datetime.timedelta(minutes=15)
    ).put()

    self.test_app.get('/cron')

    # Expect there to now be one alert each for test+1 and test+2.
    alerts = models.Alert.query().fetch()
    self.assertEqual(2, len(alerts))
    self.assertEqual(1, alerts[0].total)
    self.assertEqual(1, alerts[1].total)

    # We don't know what order our datastore query returned the alerts in.
    self.assertIn('test+1@example.com', [alert.sender for alert in alerts])
    self.assertIn('test+2@example.com', [alert.sender for alert in alerts])


class RequestHandlerTest(testing.AppengineTestCase):
  """Unit tests for app.RequestHandler."""
  app_module = app.app

  def test_get(self):
    """Tests that RequestHandler can serve GET requests."""
    response = self.test_app.get('/')
    self.assertEquals(200, response.status_code)
