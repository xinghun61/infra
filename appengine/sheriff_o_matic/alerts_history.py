# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from alerts import AlertsHandler
from alerts import AlertsJSON
from internal_alerts import InternalAlertsHandler
import json
import webapp2

from google.appengine.api import users
from google.appengine.datastore import datastore_query
from google.appengine.ext import ndb


class AlertsHistory(webapp2.RequestHandler):
  MAX_LIMIT_PER_PAGE = 100
  PUBLIC_TYPE = AlertsHandler.ALERT_TYPE
  PRIVATE_TYPE = InternalAlertsHandler.ALERT_TYPE

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
            result.type, result.gcs_filename)
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
      query = query.filter(AlertsJSON.type == self.PUBLIC_TYPE)
    else:
      query = query.filter(AlertsJSON.type.IN([self.PUBLIC_TYPE,
                                                      self.PRIVATE_TYPE]))

    if key:
      result_json.update(self.get_entry(query, key))
    else:
      result_json.update(self.get_list(query))

    self.response.headers['Content-Type'] = 'application/json'
    self.response.headers['Access-Control-Allow-Origin'] = '*'

    self.response.out.write(json.dumps(result_json))


app = webapp2.WSGIApplication([
    ('/alerts-history', AlertsHistory),
    ('/alerts-history/(.*)', AlertsHistory)
])
