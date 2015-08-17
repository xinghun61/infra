# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime
import json
import logging
import utils
import webapp2
import zlib

import cloudstorage as gcs

from google.appengine.api import app_identity
from google.appengine.api import memcache
from google.appengine.ext import ndb

LOGGER = logging.getLogger(__name__)


class AlertsJSON(ndb.Model):
  type = ndb.StringProperty()
  json = ndb.BlobProperty(compressed=True)
  date = ndb.DateTimeProperty(auto_now_add=True)
  # TODO(remove this property)
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
    data['last_posted'] = None
    last_updated = ndb.Key(LastUpdated, self.ALERT_TYPE).get()
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
    self.send_json_headers()
    self.response.write(data)
    return True

  @staticmethod
  def generate_json_dump(alerts):
    return json.dumps(alerts, cls=utils.DateTimeEncoder, indent=1)

  @staticmethod
  def get_last_datastore(alerts_type):
    #TODO(stip): rewrite to use hardcoded '-last' key to avoid race condition.
    last_query = AlertsJSON.query().filter(AlertsJSON.type == alerts_type)
    return last_query.order(-AlertsJSON.date).get()

  @staticmethod
  def get_from_gcs(alerts_type, filename):
    with contextlib.closing(gcs.open(
        "/" + app_identity.get_default_gcs_bucket_name() +
        "/history/" + alerts_type + "/" + filename)) as gcs_file:
      return gcs_file.read()
    logging.info('Reading alerts from GCS')

  def post_to_gcs(self, data):
    # Create a GCS file with GCS client.
    filename = datetime.datetime.utcnow().strftime("%Y/%M/%d/%H.%M.%S.%f")
    with contextlib.closing(gcs.open(
        "/" + app_identity.get_default_gcs_bucket_name() +
        "/history/" + self.ALERT_TYPE + "/" + filename, 'w')) as f:
      f.write(data)

    return filename

  def get_from_datastore(self):
    last_entry = self.get_last_datastore(self.ALERT_TYPE)
    if last_entry:
      logging.info('Reading alerts from datastore')
      data  = last_entry.json
      if last_entry.gcs_filename:
        data = self.get_from_gcs(self.ALERT_TYPE, last_entry.gcs_filename)
      data = json.loads(data)
      data['key'] = last_entry.key.integer_id()
      return data
    return False

  def get_from_memcache(self):
    compressed = memcache.get(self.ALERT_TYPE)
    if compressed:
      logging.info('Reading alerts from memcache')
      uncompressed = zlib.decompress(compressed)
      data = json.loads(uncompressed)
      return data
    return False

  def get(self):
    data = self.get_from_memcache() or self.get_from_datastore()
    if data:
      self.send_json_data(data)
    else:
      self.response.write({})

  def store_alerts(self, alerts):
    last_entry = self.get_last_datastore(self.ALERT_TYPE)
    last_alerts = {}
    if last_entry:
      if last_entry.gcs_filename:
        alerts_json = self.get_from_gcs(self.ALERT_TYPE,
                                        last_entry.gcs_filename)
        last_alerts = json.loads(alerts_json)
      else:
        last_alerts = json.loads(last_entry.json)

    # Only changes to the fields with 'alerts' in the name should cause a
    # new history entry to be saved.
    def alert_fields(alerts_json):
      filtered_json = {}
      for key, value in alerts_json.iteritems():
        if 'alerts' in key:
          filtered_json[key] = value
      return filtered_json

    haddiff = alert_fields(last_alerts) != alert_fields(alerts)
    if haddiff or not last_entry:
      json_data = self.generate_json_dump(alerts)

      compression_level = 9
      compressed = zlib.compress(json_data, compression_level)

      if len(compressed) < self.MAX_JSON_SIZE:
        memcache.set(self.ALERT_TYPE, compressed)
        new_entry = AlertsJSON(
            json=json_data,
            type=self.ALERT_TYPE)
        new_entry.put()
      else:
        memcache.delete(self.ALERT_TYPE)
        filename = self.post_to_gcs(json_data)
        new_entry = AlertsJSON(
           gcs_filename=filename,
           type=self.ALERT_TYPE)
        new_entry.put()
    updated_key = ndb.Key(LastUpdated, self.ALERT_TYPE)
    LastUpdated(
        key=updated_key,
        haddiff=haddiff,
        type=self.ALERT_TYPE).put()

  def update_alerts(self):
    try:
      alerts = json.loads(self.request.body)
    except ValueError:
      warning = 'Content field was not valid JSON string.'
      self.response.set_status(400, warning)
      LOGGER.warn(warning)
      return
    if alerts:
      alerts.update({'date': datetime.datetime.utcnow()})
      self.store_alerts(alerts)

  def post(self):
    self.update_alerts()


class NewAlertsHandler(AlertsHandler):
  # pylint: disable=arguments-differ
  def get(self, tree):
    self.ALERT_TYPE = 'new-alerts/%s' % tree
    super(NewAlertsHandler, self).get()

  # pylint: disable=arguments-differ
  def post(self, tree):
    self.ALERT_TYPE = 'new-alerts/%s' % tree
    super(NewAlertsHandler, self).post()


app = webapp2.WSGIApplication([
    ('/alerts', AlertsHandler),
    ('/api/v1/alerts/(.*)', NewAlertsHandler)
])
