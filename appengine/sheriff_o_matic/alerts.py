# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
import contextlib
import datetime
import datetime_encoder
import json
import logging
import webapp2
import zlib

import cloudstorage as gcs

from google.appengine.api import app_identity
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.datastore import datastore_query
from google.appengine.ext import ndb

LOGGER = logging.getLogger(__name__)


class AlertsJSON(ndb.Model):
  type = ndb.StringProperty()
  json = ndb.BlobProperty(compressed=True)
  date = ndb.DateTimeProperty(auto_now_add=True)
  # TODO(remove this property
  use_gcs = ndb.BooleanProperty()
  gcs_filename = ndb.StringProperty()


class LastUpdated(ndb.Model):
  date = ndb.DateTimeProperty(auto_now=True)
  type = ndb.StringProperty()
  haddiff = ndb.BooleanProperty()


class AlertsHandler(webapp2.RequestHandler):
  ALERT_TYPE = 'alerts'
  # Max number of bytes that AppEngine allows writing to Memcache
  MAX_JSON_SIZE = 10**6 - 10**5

  # New alerts should be posted at least every 30 minutes
  MAX_STALENESS = 60*30

  # Has no 'response' member.
  # pylint: disable=E1101
  def send_json_headers(self):
    self.response.headers['Access-Control-Allow-Origin'] = '*'
    self.response.headers['Content-Type'] = 'application/json'

  # Has no 'response' member.
  # pylint: disable=E1101
  def send_json_data(self, data):
    self.send_json_headers()
    self.response.write(data)

  @staticmethod
  def generate_json_dump(alerts):
    return json.dumps(alerts, cls=datetime_encoder.DateTimeEncoder, indent=1)

  @staticmethod
  def get_last_datastore(alerts_type):
    #TODO(stip): rewrite to use hardcoded '-last' key to avoid race condition.
    last_query = AlertsJSON.query().filter(AlertsJSON.type == alerts_type)
    return last_query.order(-AlertsJSON.date).get()

  @staticmethod
  def get_from_gcs(alerts_type, filename):
    try:
      with contextlib.closing(gcs.open(
          "/" + app_identity.get_default_gcs_bucket_name() +
          "/history/" + alerts_type + "/" + filename)) as gcs_file:
        return gcs_file.read()
    except gcs.NotFoundError:
      return '{}'
    logging.info('Reading alerts from GCS')

  def post_to_gcs(self, alerts_type, data):
    # Create a GCS file with GCS client.
    filename = datetime.datetime.utcnow().strftime("%Y/%M/%d/%H.%M.%S.%f")
    with contextlib.closing(gcs.open(
        "/" + app_identity.get_default_gcs_bucket_name() +
        "/history/" + alerts_type + "/" + filename, 'w')) as f:
      f.write(data)

    return filename

  def get_from_datastore(self, alerts_type):
    last_entry = self.get_last_datastore(alerts_type)
    if last_entry:
      logging.info('Reading alerts from datastore')
      data  = last_entry.json
      if last_entry.gcs_filename:
        data = self.get_from_gcs(alerts_type, last_entry.gcs_filename)
      data = json.loads(data)
      data['key'] = last_entry.key.integer_id()
      data['stale_alerts_thresh'] = self.MAX_STALENESS

      data['last_posted'] = None
      last_updated = ndb.Key(LastUpdated, alerts_type).get()
      if last_updated:
        data['last_posted'] = (last_updated.date -
            datetime.datetime.utcfromtimestamp(0)).total_seconds()

      utcnow = (datetime.datetime.utcnow() -
          datetime.datetime.utcfromtimestamp(0))
      posted_date = data['date']
      if data['last_posted']:
        posted_date = data['last_posted']
      if utcnow.total_seconds() - posted_date > self.MAX_STALENESS:
        data['stale_alerts_json'] = True

      data = self.generate_json_dump(data)

      self.send_json_data(data)
      return True
    return False

  def get_from_memcache(self, memcache_key):
    compressed = memcache.get(memcache_key)
    if compressed:
      logging.info('Reading alerts from memcache')
      uncompressed = zlib.decompress(compressed)
      data = json.loads(uncompressed)

      data['last_posted'] = None
      last_updated = ndb.Key(LastUpdated, memcache_key).get()
      if last_updated:
        data['last_posted'] = (last_updated.date -
            datetime.datetime.utcfromtimestamp(0)).total_seconds()

      utcnow = (datetime.datetime.utcnow() -
          datetime.datetime.utcfromtimestamp(0))
      posted_date = data['date']
      if data['last_posted']:
        posted_date = data['last_posted']
      if utcnow.total_seconds() - posted_date > self.MAX_STALENESS:
        data['stale_alerts_json'] = True
      data['stale_alerts_thresh'] = self.MAX_STALENESS

      data = self.generate_json_dump(data)
      self.send_json_data(data)
      return True
    return False

  def get_alerts(self, alerts_type):
    self.send_json_headers()
    if not self.get_from_memcache(alerts_type):
      if not self.get_from_datastore(alerts_type):
        self.send_json_data({})

  def get(self):
    self.get_alerts(self.ALERT_TYPE)

  def store_alerts(self, alerts_type, alerts):
    last_entry = self.get_last_datastore(alerts_type)
    last_alerts = {}
    if last_entry:
      if last_entry.gcs_filename:
        alerts_json = self.get_from_gcs(alerts_type, last_entry.gcs_filename)
        last_alerts = json.loads(alerts_json)
      else:
        last_alerts = json.loads(last_entry.json) if last_entry else {}

    # Only changes to the fields with 'alerts' in the name should cause a
    # new history entry to be saved.
    def alert_fields(alerts_json):
      filtered_json = {}
      for key, value in alerts_json.iteritems():
        if 'alerts' in key:
          filtered_json[key] = value
      return filtered_json

    haddiff = alert_fields(last_alerts) != alert_fields(alerts)
    if haddiff:
      json_data = self.generate_json_dump(alerts)

      compression_level = 9
      compressed = zlib.compress(json_data, compression_level)

      if len(compressed) < self.MAX_JSON_SIZE:
        memcache.set(alerts_type, compressed)
        new_entry = AlertsJSON(
            json=json_data,
            type=alerts_type)
        new_entry.put()
      else:
        memcache.delete(alerts_type)
        filename = self.post_to_gcs(alerts_type, json_data)
        new_entry = AlertsJSON(
           gcs_filename=filename,
           type=alerts_type)
        new_entry.put()
    updated_key = ndb.Key(LastUpdated, alerts_type)
    LastUpdated(
        key=updated_key,
        haddiff=haddiff,
        type=alerts_type).put()


  def parse_alerts(self, alerts_json):
    try:
      alerts = json.loads(alerts_json)
    except ValueError:
      warning = 'content field was not JSON'
      self.response.set_status(400, warning)
      LOGGER.warn(warning)
      return

    alerts.update({'date': datetime.datetime.utcnow()})

    return alerts

  def update_alerts(self, alerts_type):
    content = json.loads(self.request.body).get('content')
    alerts = self.parse_alerts(content)

    if alerts:
      self.store_alerts(alerts_type, alerts)

  def post(self):
    self.update_alerts(self.ALERT_TYPE)


class AlertsHistory(webapp2.RequestHandler):
  MAX_LIMIT_PER_PAGE = 100

  def get_entry(self, query, key):
    try:
      key = int(key)
    except ValueError:
      self.response.set_status(400, 'Invalid key format')
      self.abort(400)

    ndb_key = ndb.Key(AlertsJSON, key)
    result = query.filter(AlertsJSON.key == ndb_key).get()
    if result:
      if result.gcs_filename:
        result.json = AlertsHandler.get_from_gcs(
            AlertsHandler.ALERT_TYPE, result.gcs_filename)
      data = json.loads(result.json)
      data['key'] = key
      return data
    else:
      self.response.set_status(404, 'Failed to find key %s' % key)
      self.abort(404)

  def get_list(self, query):
    cursor = self.request.get('cursor')
    if cursor:
      cursor = datastore_query.Cursor(urlsafe=cursor)

    limit = int(self.request.get('limit', self.MAX_LIMIT_PER_PAGE))
    limit = min(self.MAX_LIMIT_PER_PAGE, limit)

    if cursor:
      alerts, next_cursor, has_more = query.fetch_page(limit,
                                                       start_cursor=cursor)
    else:
      alerts, next_cursor, has_more = query.fetch_page(limit)

    return {
        'has_more': has_more,
        'cursor': next_cursor.urlsafe() if next_cursor else '',
        'history': [alert.key.integer_id() for alert in alerts]
    }

  def get(self, key=None):
    query = AlertsJSON.query().order(-AlertsJSON.date)
    result_json = {}

    user = users.get_current_user()
    result_json['login-url'] = users.create_login_url(self.request.uri)

    # Return only public alerts for non-internal users.
    if not user or not user.email().endswith('@google.com'):
      query = query.filter(AlertsJSON.type == AlertsHandler.ALERT_TYPE)

    if key:
      result_json.update(self.get_entry(query, key))
    else:
      result_json.update(self.get_list(query))

    self.response.headers['Content-Type'] = 'application/json'
    self.response.headers['Access-Control-Allow-Origin'] = '*'

    self.response.out.write(json.dumps(result_json))


class NewAlertsHandler(AlertsHandler):
  ALERTS_TYPE = 'new-alerts'

  def get(self):
    super(NewAlertsHandler, self).get_alerts(
        NewAlertsHandler.ALERTS_TYPE)

  def post(self):
    self.update_alerts(NewAlertsHandler.ALERTS_TYPE)


app = webapp2.WSGIApplication([
    ('/alerts', AlertsHandler),
    ('/api/v1/alerts', NewAlertsHandler),
    ('/alerts-history', AlertsHistory),
    ('/alerts-history/(.*)', AlertsHistory),
])
