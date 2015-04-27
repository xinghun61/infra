# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import googleapiclient.http
import httplib2
import json
import logging
import os
import traceback
import webapp2

from google.appengine.api import app_identity
from google.appengine.ext import ndb

import common


def _get_config_data():
  data_entity = common.MonAcqData.get_by_id(common.CONFIG_DATA_KEY)
  logging.info('get_config_data(): entity = %r', data_entity)
  if not data_entity:
    return None
  return data_entity.to_dict()


def _get_credentials(credentials_dict, scopes):
  """Obtain Aquisition API credentials as Credentials object."""
  from oauth2client.client import SignedJwtAssertionCredentials

  # Ideally, we should have loaded credentials with GoogleCredentials.
  # However, it insists to load only from a file. So, here's a hack.
  return SignedJwtAssertionCredentials(
      service_account_name=credentials_dict['client_email'],
      private_key=credentials_dict['private_key'],
      scope=scopes,
      # Extra **kwargs, just in case.
      service_account_id=credentials_dict['client_id'],
      private_key_id=credentials_dict['private_key_id'],
  )


class VMHandler(webapp2.RequestHandler):

  def requester_is_me(self):
    requester_id = self.request.headers.get('X-Appengine-Inbound-Appid')
    return requester_id == app_identity.get_application_id()

  def requester_is_task(self):
    return bool(self.request.headers.get('X-AppEngine-TaskName'))

  def post(self):
    authorized = (
        common.is_development_server() or
        self.requester_is_task() or self.requester_is_me())
    if not authorized:
      self.abort(403)
    data = _get_config_data()
    if not data:
      self.abort_admin_error('Endpoint data is not set')
    if not all(f in data for f in ['credentials', 'url']):
      self.abort_admin_error('Missing required fields: credentials, url')

    url = data['url']
    http_auth = httplib2.Http()
    try:
      credentials = _get_credentials(data['credentials'], data['scopes'])
    except KeyError as e:
      self.abort_admin_error('Bad credentials format: missing field %s' % e)
    http_auth = credentials.authorize(http_auth)
    def callback(response, _content):
      success = 200 <= response.status and response.status <= 299
      if not success:
        logging.error('Failed to send data to %s: %d %s',
                      url, response.status, response.reason)
    # Important: set content-type to binary, otherwise httplib2 mangles it.
    data.setdefault('headers', {}).update({
        'content-length': str(len(self.request.body)),
        'content-type': 'application/x-protobuf',
    })
    request = googleapiclient.http.HttpRequest(
        http_auth, callback, url, method='POST', body=self.request.body,
        headers=data['headers'])
    logging.debug('Sending the payload (synchronously).')
    request.execute()
    logging.debug('Done sending the payload.')

  def abort_admin_error(self, message):
      logging.error('%s; please visit https://%s/admin/',
                    message, app_identity.get_default_version_hostname())
      self.abort(500)


logging.basicConfig(level=logging.DEBUG)
app = webapp2.WSGIApplication([
    ('/vm.*', VMHandler),
    ], debug=True)
