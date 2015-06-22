# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import alerts
import internal_alerts
import logging
import webapp2

from google.appengine.api import users

ALLOWED_APP_IDS = ('google.com:monarch-email-alerts-parser')
INBOUND_APP_ID = 'X-Appengine-Inbound-Appid'


class TimeSeriesInternalAlertsHandler(internal_alerts.InternalAlertsHandler):
  ALERT_TYPE = 'ts-internal-alerts'

  def post(self):
    app_id = self.request.headers.get(INBOUND_APP_ID, None)
    if app_id and app_id in ALLOWED_APP_IDS:
      self.update_alerts(self.ALERT_TYPE)
    else:
      logging.info('Permission denied.')
      self.abort(403)


class TimeSeriesAlertsHandler(alerts.AlertsHandler):
  ALERT_TYPE = 'ts-alerts'

  def post(self):
    app_id = self.request.headers.get(INBOUND_APP_ID, None)
    if app_id and app_id in ALLOWED_APP_IDS:
      self.update_alerts(self.ALERT_TYPE)
    else:
      logging.info('Permission denied.')
      self.abort(403)


app = webapp2.WSGIApplication([
    ('/ts-alerts', TimeSeriesAlertsHandler),
    ('/ts-internal-alerts', TimeSeriesInternalAlertsHandler)])
