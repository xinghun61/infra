# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import sys
import webapp2

from webapp2_extras import jinja2

import common
import handler_utils
from components import auth
from components import utils


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
    params['url'] = data.url or ''
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
        'xsrf_token': self._handler.generate_xsrf_token(),
    }
    data = common.MonAcqData.get_by_id(common.CONFIG_DATA_KEY)
    if data:
      self.setParams(params, data)
    self.render_response('set_credentials.html', **params)

  def post(self):
    params = {
        'message': '',
        'title': 'Config: Chrome Infra Monitoring Proxy',
        'xsrf_token': self._handler.generate_xsrf_token(),
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


class AdminDispatch(handler_utils.BaseAuthHandler):
  """Provide a cached Jinja environment to each request."""

  @auth.autologin
  @auth.require(lambda: auth.is_group_member(
      'project-chrome-infra-monitoring-team'))
  def get(self, command):
    commands[command](self).get()

  @auth.require(lambda: auth.is_group_member(
      'project-chrome-infra-monitoring-team'))
  def post(self, command):
    commands[command](self).post()


def create_app():
  if utils.is_local_dev_server():
    handler_utils.init_local_dev_server()

  admin_handlers = [
      (r'/admin/(.*)', AdminDispatch),
  ]

  return webapp2.WSGIApplication(admin_handlers, debug=True)
