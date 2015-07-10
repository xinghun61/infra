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
    data = {'alerts': data}
    data['last_posted'] = None
    last_updated = ndb.Key(alerts.LastUpdated, self.ALERT_TYPE).get()
    if last_updated:
      data['last_posted'] = (last_updated.date -
          datetime.datetime.utcfromtimestamp(0)).total_seconds()

    self.send_json_headers()
    self.response.write(self.generate_json_dump(data))

  def update_db(self, new_alerts):
    json_data = self.generate_json_dump(new_alerts)

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
        haddiff=True,
        type=self.ALERT_TYPE).put()

  def delete(self, ind):
    old_alerts = self.get_from_memcache() or self.get_from_datastore() or []

    try:
      del old_alerts[int(ind)]
      self.update_db(old_alerts)
      self.response.write("Deleted ts-alert.")
    except IndexError:
      self.response.write("Alert does not exist.")

  def store_alerts(self, alert):
    old_alerts = self.get_from_memcache() or self.get_from_datastore() or []

    def find_alert(old_alerts, new_alert):
      for ind, old_alert in enumerate(old_alerts):
        if (old_alert['condition_name'] == new_alert['condition_name'] and
           old_alert['active_since'] == new_alert['active_since']):
          return ind
      return -1

    if find_alert(old_alerts, alert) == -1:
      old_alerts.append(alert)
      logging.info('storing a new ts-alert')
      self.update_db(old_alerts)

  def get_from_datastore(self):
    db = alerts.AlertsJSON
    query = db.query().filter(db.type == self.ALERT_TYPE)
    last_entry = query.order(-db.date).get()
    if last_entry:
      logging.info('Reading alerts from datastore')
      data  = last_entry.json
      data = json.loads(last_entry.json)
      return data
    return False

  def get(self):
    data = self.get_from_memcache() or self.get_from_datastore() or []
    self.send_json_data(data)


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
    if not email.endswith('@google.com') and '+' not in email:
      self.response.set_status(403, 'Permission denied.')
      return

    super(TimeSeriesInternalAlertsHandler, self).get()

class TimeSeriesAlertsHistory(alerts_history.AlertsHistory):
  PUBLIC_TYPE = TimeSeriesAlertsHandler.ALERT_TYPE
  PRIVATE_TYPE = TimeSeriesInternalAlertsHandler.ALERT_TYPE

  def get_entry(self, query, key):
    try:
      key = int(key)
    except ValueError:
      self.response.set_status(400, 'Invalid key format')
      self.abort(400)

    ndb_key = ndb.Key(alerts.AlertsJSON, key)
    result = query.filter(alerts.AlertsJSON.key == ndb_key).get()
    if result:
      data = {}
      data['alerts'] = json.loads(result.json)
      data['key'] = key
      return data
    else:
      self.response.set_status(404, 'Failed to find key %s' % key)
      self.abort(404)


app = webapp2.WSGIApplication([
    ('/ts-alerts', TimeSeriesAlertsHandler),
    ('/ts-alerts/(\d+)', TimeSeriesAlertsHandler),
    ('/ts-internal-alerts', TimeSeriesInternalAlertsHandler),
    ('/ts-alerts-history', TimeSeriesAlertsHistory),
    ('/ts-alerts-history/(.*)', TimeSeriesAlertsHistory)])
