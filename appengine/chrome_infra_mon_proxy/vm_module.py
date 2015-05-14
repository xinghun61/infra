# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import googleapiclient.http
import httplib2
import json
import logging
import os
import random
import traceback
import webapp2

from google.appengine.api import app_identity
from google.appengine.ext import ndb

import common


# Cannot use components.utils version here, because docker containers
# don't play well with non-local symlinks.
def _is_development_server():
  return os.environ.get('SERVER_SOFTWARE', '').startswith('Development')


def _get_config_data():
  data_entity = common.ConfigData.get_by_id(common.CONFIG_DATA_KEY)
  if not data_entity:
    return None
  return data_entity


def _get_credentials(credentials, scopes):
  """Obtain Aquisition API credentials as Credentials object."""
  if not credentials.client_email:
    return None

  # TODO(sergeyberezin): migrate to using ServiceAccountKey.
  # See https://goo.gl/Q57gm3.
  from oauth2client.client import SignedJwtAssertionCredentials

  return SignedJwtAssertionCredentials(
      service_account_name=credentials.client_email,
      private_key=credentials.private_key,
      scope=scopes,
      # Extra **kwargs, just in case.
      service_account_id=credentials.client_id,
      private_key_id=credentials.private_key_id,
  )


class VMHandler(webapp2.RequestHandler):

  def requester_is_me(self):
    requester_id = self.request.headers.get('X-Appengine-Inbound-Appid')
    return requester_id == app_identity.get_application_id()

  def requester_is_task(self):
    return bool(self.request.headers.get('X-AppEngine-TaskName'))

  def post(self, ip):
    authorized = (
        _is_development_server() or
        self.requester_is_task() or self.requester_is_me())
    if not authorized:
      self.abort(403)
    data = _get_config_data()
    if not data:
      self.abort_admin_error('Endpoints are not defined')

    http_auth = httplib2.Http()
    # Make the traffic split deterministic in the source IP.
    random.seed(ip)
    if random.uniform(0, 100) < data.secondary_endpoint_load:
      endpoint = data.secondary_endpoint
    else:
      endpoint = data.primary_endpoint
    credentials = _get_credentials(endpoint.credentials, endpoint.scopes)
    url = endpoint.url
    if credentials:
      http_auth = credentials.authorize(http_auth)
    def callback(response, _content):
      success = 200 <= response.status and response.status <= 299
      if not success:
        logging.error('Failed to send data to %s: %d %s',
                      url, response.status, response.reason)
    # Important: set correct content-type, otherwise httplib2 mangles it.
    headers = endpoint.headers
    headers.update({
        'content-length': str(len(self.request.body)),
        'content-type': 'application/x-protobuf',
    })
    request = googleapiclient.http.HttpRequest(
        http_auth, callback, url, method='POST', body=self.request.body,
        headers=headers)
    logging.debug('Sending the payload (synchronously).')
    request.execute()
    logging.debug('Done sending the payload.')

  def abort_admin_error(self, message):
      logging.error('%s; please visit https://%s/admin/',
                    message, app_identity.get_default_version_hostname())
      self.abort(500)


logging.basicConfig(level=logging.DEBUG)
app = webapp2.WSGIApplication([
    (r'/vm.*/(.*)', VMHandler),
    ], debug=True)
