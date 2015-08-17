# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import alerts_history
import json
import logging
import utils
import webapp2
import zlib

from datetime import datetime as dt
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import ndb


ALLOWED_APP_IDS = ('google.com:monarch-email-alerts-parser')
INBOUND_APP_ID = 'X-Appengine-Inbound-Appid'


class TSAlertsJSON(ndb.Model):
  active_until = ndb.DateTimeProperty()
  json = ndb.JsonProperty(compressed=True)

  @classmethod
  def query_active(cls):
    return cls.query().filter(TSAlertsJSON.active_until == None)

  @classmethod
  def query_hash(cls, key):
    return cls.get_by_id(key)


class TimeSeriesAlertsHandler(webapp2.RequestHandler):
  ALERT_TYPE = 'ts-alerts'
  MEMCACHE_COMPRESSION_LEVEL = 9
  # Alerts which have continued to fire are re-sent every 5 minutes, so stale
  # alerts older than 300 seconds are replaced by incoming alerts.
  STALE_ALERT_TIMEOUT = 300

  def get(self, key=None):
    utils.increment_monarch('ts-alerts')
    self.remove_expired_alerts()
    if not users.get_current_user():
      results = {'date': dt.utcnow(),
                 'redirect-url': users.create_login_url(self.request.uri)}
      self.write_json(results)
      return

    if key:
      logging.info('getting the key: ' + key)
      try:
        data = memcache.get(key) or TSAlertsJSON.query_hash(key).json
      except AttributeError:
        self.response.write('This alert does not exist.')
        self.response.set_status(404, 'Alert does not exist')
        return
      if not data:
        self.response.write('This alert does not exist.')
        self.response.set_status(404, 'Alert does not exist')
      elif data.get('private', True) and not utils.is_googler():
        logging.info('Permission denied.')
        self.abort(403)
      else:
        self.write_json(data.get(json, data))
    else:
      query = TSAlertsJSON.query_active().fetch()
      data = []
      for item in query:
        if item.json.get('private', True) and not utils.is_googler():
          continue
        data.append(item.json)
      self.write_json({'alerts': data})

  def post(self):
    app_id = self.request.headers.get(INBOUND_APP_ID, None)
    if app_id not in ALLOWED_APP_IDS:
      logging.info('Permission denied')
      self.abort(403)
      return
    self.update_alerts()

  def put(self, key):
    if not utils.is_googler():
      self.response.set_status(403, 'Permission Denied')
      return
    changed_alert = TSAlertsJSON.query_hash(key)
    if not changed_alert:
      self.response.write('This alert does not exist.')
      self.response.set_status(404, 'Alert does not exist')
      return
    try:
      data = json.loads(self.request.body)
    except ValueError:
      warning = ('Content %s was not valid JSON string.', self.request.body)
      self.response.set_status(400, warning)
      return
    logging.info('Alert before: ' + str(changed_alert))
    logging.info('Data: ' + str(data))
    changed_alert.json.update(data)
    logging.info('Alert after: ' + str(changed_alert))
    changed_alert.put()
    memcache.set(key, changed_alert.json)
    self.response.write("Updated ts-alerts.")

  def delete(self, key):
    if not utils.is_googler():
      self.response.set_status(403, 'Permission Denied')
      return
    if key == 'all':
      all_keys = TSAlertsJSON.query().fetch(keys_only=True)
      ndb.delete_multi(all_keys)
      for k in all_keys:
        logging.info('deleting key from memcache: ' + k.id())
        memcache.delete(k.id())
      self.response.set_status(200, 'Cleared all alerts')
      return
    changed_alert = TSAlertsJSON.query_hash(key)
    if not changed_alert:
      self.response.write('This alert does not exist.')
      self.response.set_status(404, 'Alert does not exist')
      return
    memcache.delete(key)
    changed_alert.key.delete()

  def write_json(self, data):
    self.response.headers['Access-Control-Allow-Origin'] = '*'
    self.response.headers['Content-Type'] = 'application/json'
    data = utils.generate_json_dump(data)
    self.response.write(data)

  def remove_expired_alerts(self):
    active_alerts = TSAlertsJSON.query_active().fetch()

    for alert in active_alerts:
      alert_age = utils.secs_ago(alert.json['alert_sent_utc'])
      if alert_age > self.STALE_ALERT_TIMEOUT:
        logging.info('%s expired. alert age: %d.', alert.key.id(), alert_age)
        alert.active_until = dt.utcnow()
        alert.json['active_until'] = dt.strftime(alert.active_until, '%s')
        alert.put()
        memcache.set(alert.key.id(), alert.json)

  def update_alerts(self):
    self.remove_expired_alerts()
    try:
      alerts = json.loads(self.request.body)
    except ValueError:
      warning = 'Content field was not valid JSON string.'
      self.response.set_status(400, warning)
      logging.warning(warning)
      return
    if alerts:
      self.store_alerts(alerts)

  def store_alerts(self, alert):
    pre_hash_string = alert['mash_expression'] + alert['active_since']
    hash_key = utils.hash_string(pre_hash_string)
    alert['hash_key'] = hash_key

    new_entry = TSAlertsJSON(
        id=hash_key,
        json=alert,
        active_until=None)
    new_entry.put()
    memcache.set(hash_key, alert)

  def set_memcache(self, key, data):
    json_data = utils.generate_json_dump(data, False)
    compression_level = self.MEMCACHE_COMPRESSION_LEVEL
    compressed = zlib.compress(json_data, compression_level)
    memcache.set(key, compressed)


class TimeSeriesAlertsHistory(alerts_history.AlertsHistory):

  def get(self, timestamp=None):
    utils.increment_monarch('ts-alerts-history')
    result_json = {}
    if not users.get_current_user():
      result_json['login-url'] = users.create_login_url(self.request.uri)
      return result_json

    alerts = TSAlertsJSON.query_active().fetch()
    if timestamp:
      try:
        time = dt.fromtimestamp(int(timestamp))
      except ValueError:
        self.response.set_status(400, 'Invalid timestamp.')
        return
      if time > dt.utcnow():
        self.response.write('Sheriff-o-matic cannot predict the future... yet.')
        self.response.set_status(400, 'Invalid timestamp.')
    else:
      time = dt.utcnow()
    alerts += TSAlertsJSON.query(TSAlertsJSON.active_until > time).fetch()

    history = []
    for a in alerts:
      ts, private = timestamp, a.json['private']
      in_range = not (ts and utils.secs_ago(a.json['active_since_utc'], ts) < 0)
      permission = utils.is_googler() or not private
      if in_range and permission:
        history.append(a.json)

    result_json.update({
        'timestamp': time.strftime('%s'),
        'time_string': time.strftime('%Y-%m-%d %H:%M:%S %Z'),
        'active_alerts': history
    })

    self.write_json(result_json)

  def write_json(self, data):
    self.response.headers['Access-Control-Allow-Origin'] = '*'
    self.response.headers['Content-Type'] = 'application/json'
    data = utils.generate_json_dump(data)
    self.response.write(data)


app = webapp2.WSGIApplication([
    ('/ts-alerts', TimeSeriesAlertsHandler),
    ('/ts-alerts/(.*)', TimeSeriesAlertsHandler),
    ('/ts-alerts-history', TimeSeriesAlertsHistory),
    ('/ts-alerts-history/(.*)', TimeSeriesAlertsHistory)])
