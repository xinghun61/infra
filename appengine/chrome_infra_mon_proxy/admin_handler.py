# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import sys
import webapp2

from google.appengine.api import users
from webapp2_extras import jinja2

import common

class AdminCommand(object):
  """Base class for administrative commands.

  Implement get() and post() methods in the subclasses.
  """

  def __init__(self, handler):
    self._handler = handler

  @property
  def request(self):
    return self._handler.request

  @property
  def response(self):
    return self._handler.response

  def render_response(self, _template, **context):
    self._handler.render_response(_template, **context)


class AdminPage(AdminCommand):
  """Display the admin page."""

  def get(self):
    context = {'title': 'Admin: Chrome Infra Monitoring Proxy'}
    self.render_response('admin.html', **context)

  def post(self):
    self.response.set_status(403)
    return


class SetCredentials(AdminCommand):
  """Save new credentials for the Monacq endpoint."""

  @staticmethod
  def setParams(params, data):
    """Serialize data fields into template parameters."""
    params['url'] = data.url
    params['credentials'] = json.dumps(data.credentials)
    params['scopes'] = '\n'.join(data.scopes)
    params['headers'] = json.dumps(data.headers)

  # Deserialize form fields. It is an inverse of setParams().
  _parsers = {
      'url': lambda v: v,
      'credentials': json.loads,
      'scopes': lambda v: [l.strip() for l in v.splitlines() if l],
      'headers': json.loads,
  }

  def get(self):
    params = {
        'message': '',
        'title': 'Config: Chrome Infra Monitoring Proxy',
    }
    data = common.MonAcqData.get_by_id(common.CONFIG_DATA_KEY)
    if data:
      self.setParams(params, data)
    self.render_response('set_credentials.html', **params)

  def post(self):
    params = {
        'message': '',
        'title': 'Config: Chrome Infra Monitoring Proxy',
    }
    data = common.MonAcqData.get_or_insert(common.CONFIG_DATA_KEY)
    self.setParams(params, data)

    updated_fields = False
    failed_fields = []
    for field, parser in self._parsers.iteritems():
      if not self.request.get(field):
        continue
      try:
        setattr(data, field, parser(self.request.get(field)))
        updated_fields = True
      except ValueError:
        failed_fields.append(field)
      params[field] = self.request.get(field)

    if failed_fields:
      params['message'] = 'Failed to update %s. Please try again.' % (
          ', '.join(failed_fields))
    elif updated_fields:
      data.put()
      self.setParams(params, data)
      params['message'] = 'Updated configuration.'
      logging.info('Updated configuration: %r', data)
    self.render_response('set_credentials.html', **params)


commands = {
  '': AdminPage,
  'set-credentials': SetCredentials,
}


# TODO(sergeyberezin): reimplement this using auth groups.
class AdminDispatch(common.BaseHandler):
  """Provide a cached Jinja environment to each request."""

  def get(self, command):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.url))
      return
    if not users.is_current_user_admin():
      self.response.set_status(403)
      return
    commands[command](self).get()

  def post(self, command):
    if not users.is_current_user_admin():
      self.response.set_status(403)
      return
    commands[command](self).post()


admin_handlers = [
    (r'/admin/(.*)', AdminDispatch),
]

admin = webapp2.WSGIApplication(admin_handlers, debug=True)
