# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import alerts
import alerts_history
import datetime
import json
import logging
import webapp2
import zlib

from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import ndb

ALLOWED_APP_IDS = ('google.com:monarch-email-alerts-parser')
INBOUND_APP_ID = 'X-Appengine-Inbound-Appid'


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

  def store_alerts(self, alert):
    last_entry = self.get_last_datastore(self.ALERT_TYPE)
    last_alerts = json.loads(last_entry.json) if last_entry else {}

    if last_alerts != alert:
      json_data = self.generate_json_dump(alert)

      compression_level = 9
      compressed = zlib.compress(json_data, compression_level)

      memcache.set(self.ALERT_TYPE, compressed)
      new_entry = alerts.AlertsJSON(
          json=json_data,
          type=self.ALERT_TYPE)
      new_entry.put()

    updated_key = ndb.Key(alerts.LastUpdated, self.ALERT_TYPE)
    alerts.LastUpdated(
        key=updated_key,
        haddiff=last_alerts!=alerts,
        type=self.ALERT_TYPE).put()


class TimeSeriesInternalAlertsHandler(TimeSeriesAlertsHandler):
  ALERT_TYPE = 'ts-internal-alerts'

  def get(self):
    user = users.get_current_user()
    if not user:
      ret = {}
      ret.update({
          'date': datetime.datetime.utcnow(),
          'redirect-url': users.create_login_url(self.request.uri)})
      data = self.generate_json_dump(ret)
      self.send_json_headers()
      self.response.write(data)
      return

    email = user.email()
    if not email.endswith('@google.com'):
      self.response.set_status(403, 'Permission denied.')
      return

    super(TimeSeriesInternalAlertsHandler, self).get()

class TimeSeriesAlertsHistory(alerts_history.AlertsHistory):
  PUBLIC_TYPE = TimeSeriesAlertsHandler.ALERT_TYPE
  PRIVATE_TYPE = TimeSeriesInternalAlertsHandler.ALERT_TYPE


app = webapp2.WSGIApplication([
    ('/ts-alerts', TimeSeriesAlertsHandler),
    ('/ts-internal-alerts', TimeSeriesInternalAlertsHandler),
    ('/ts-alerts-history', TimeSeriesAlertsHistory),
    ('/ts-alerts-history/(.*)', TimeSeriesAlertsHistory)])
