# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import alerts
import alerts_history
import datetime
import internal_alerts
import logging
import webapp2

from google.appengine.api import users
from google.appengine.ext import ndb

ALLOWED_APP_IDS = ('google.com:monarch-email-alerts-parser')
INBOUND_APP_ID = 'X-Appengine-Inbound-Appid'


class TimeSeriesInternalAlertsHandler(internal_alerts.InternalAlertsHandler):
  ALERT_TYPE = 'ts-internal-alerts'

  def post(self):
    app_id = self.request.headers.get(INBOUND_APP_ID, None)
    if app_id and app_id in ALLOWED_APP_IDS:
      self.update_alerts()
    else:
      logging.info('Permission denied.')
      self.abort(403)

  def send_json_data(self, data):
    data['last_posted'] = None
    last_updated = ndb.Key(alerts.LastUpdated, self.ALERT_TYPE).get()
    if last_updated:
      data['last_posted'] = (last_updated.date -
          datetime.datetime.utcfromtimestamp(0)).total_seconds()

    data = self.generate_json_dump(data)
    self.response.write(data)


class TimeSeriesAlertsHandler(alerts.AlertsHandler):
  ALERT_TYPE = 'ts-alerts'

  def post(self):
    app_id = self.request.headers.get(INBOUND_APP_ID, None)
    if app_id and app_id in ALLOWED_APP_IDS:
      self.update_alerts()
    else:
      logging.info('Permission denied.')
      self.abort(403)

  def send_json_data(self, data):
    data['last_posted'] = None
    last_updated = ndb.Key(alerts.LastUpdated, self.ALERT_TYPE).get()
    if last_updated:
      data['last_posted'] = (last_updated.date -
          datetime.datetime.utcfromtimestamp(0)).total_seconds()

    data = self.generate_json_dump(data)
    self.response.write(data)


class TimeSeriesAlertsHistory(alerts_history.AlertsHistory):
  PUBLIC_TYPE = TimeSeriesAlertsHandler.ALERT_TYPE
  PRIVATE_TYPE = TimeSeriesInternalAlertsHandler.ALERT_TYPE


app = webapp2.WSGIApplication([
    ('/ts-alerts', TimeSeriesAlertsHandler),
    ('/ts-internal-alerts', TimeSeriesInternalAlertsHandler),
    ('/ts-alerts-history', TimeSeriesAlertsHistory),
    ('/ts-alerts-history/(.*)', TimeSeriesAlertsHistory)])
