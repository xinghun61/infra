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


def updateCredentials(model, credentials_json):
  parsed = json.loads(credentials_json or '{}')
  model.client_email = parsed.get('client_email', '')
  model.private_key = parsed.get('private_key', '')
  model.private_key_id = parsed.get('private_key_id', '')
  model.client_id = parsed.get('client_id', '')


def updateConfig(config, field, value):
  logging.info('updateConfig(%s, %r)', field, value)
  if 'primary_url' == field:
    config.primary_endpoint.url = value.strip()
  elif 'secondary_url' == field:
    config.secondary_endpoint.url = value.strip()
  elif 'secondary_endpoint_load' == field:
    config.secondary_endpoint_load = int(value or '0')
  elif 'primary_credentials' == field:
    updateCredentials(config.primary_endpoint.credentials, value.strip())
  elif 'secondary_credentials' == field:
    updateCredentials(config.secondary_endpoint.credentials, value.strip())
  elif 'primary_scopes' == field:
    config.primary_endpoint.scopes = [
        l.strip() for l in value.splitlines() if l]
  elif 'secondary_scopes' == field:
    config.secondary_endpoint.scopes = [
        l.strip() for l in value.splitlines() if l]
  elif 'primary_headers' == field:
    config.primary_endpoint.headers = json.loads(value or '{}')
  elif 'secondary_headers' == field:
    config.secondary_endpoint.headers = json.loads(value or '{}')
  else:  # Break unittests if this ever happens.
    raise Exception('updateConfig: unknown field %s' % field)


class SetCredentials(AdminCommand):
  """Save new credentials for the Monacq endpoint."""

  @staticmethod
  def setParams(params, data):
    """Serialize data fields into template parameters."""
    params['primary_url'] = data.primary_endpoint.url or ''
    params['secondary_url'] = data.secondary_endpoint.url or ''
    params['secondary_endpoint_load'] = data.secondary_endpoint_load
    params['primary_credentials'] = json.dumps(
        data.primary_endpoint.credentials.to_dict())
    params['secondary_credentials'] = json.dumps(
        data.secondary_endpoint.credentials.to_dict())
    params['primary_scopes'] = '\n'.join(data.primary_endpoint.scopes)
    params['secondary_scopes'] = '\n'.join(data.secondary_endpoint.scopes)
    params['primary_headers'] = json.dumps(data.primary_endpoint.headers)
    params['secondary_headers'] = json.dumps(data.secondary_endpoint.headers)

  fields = ['primary_url', 'secondary_url', 'secondary_endpoint_load',
            'primary_credentials', 'secondary_credentials',
            'primary_scopes', 'secondary_scopes',
            'primary_headers', 'secondary_headers']

  def get(self):
    params = {
        'message': '',
        'title': 'Config: Chrome Infra Monitoring Proxy',
        'xsrf_token': self._handler.generate_xsrf_token(),
    }
    data = common.ConfigData.get_or_insert(common.CONFIG_DATA_KEY)
    logging.debug('SetCredentials.get(): data = %r', data)
    self.setParams(params, data)
    self.render_response('set_credentials.html', **params)

  def post(self):
    params = {
        'message': '',
        'title': 'Config: Chrome Infra Monitoring Proxy',
        'xsrf_token': self._handler.generate_xsrf_token(),
    }
    data = common.ConfigData.get_or_insert(common.CONFIG_DATA_KEY)
    self.setParams(params, data)

    failed_fields = []
    for field in self.fields:
      logging.info('set_credentials.post: %s = %r',
                   field, self.request.get(field))
      try:
        updateConfig(data, field, self.request.get(field))
      except ValueError:
        failed_fields.append(field)
        logging.warning('set_credentials.post: failed to update %s with %r',
                        field, self.request.get(field))
      params[field] = self.request.get(field)

    if failed_fields:
      params['message'] = 'Failed to update %s. Please try again.' % (
          ', '.join(failed_fields))
    else:
      data.put()
      self.setParams(params, data)
      params['message'] = 'Updated configuration.'
      logging.info('Updated configuration: %r', data.to_dict())
    data = common.ConfigData.get_by_id(common.CONFIG_DATA_KEY)
    self.render_response('set_credentials.html', **params)


class SetTraffic(AdminCommand):
  def get(self):
    params = {
        'message': '',
        'title': 'Traffic: Chrome Infra Monitoring Proxy',
        'xsrf_token': self._handler.generate_xsrf_token(),
    }
    data = common.TrafficSplit.get_or_insert(common.TRAFFIC_SPLIT_KEY)
    config = common.ConfigData.get_or_insert(common.CONFIG_DATA_KEY)
    params.update(data.to_dict())
    params.update({'secondary_endpoint_load': config.secondary_endpoint_load})
    self.render_response('set_traffic.html', **params)

  def post(self):
    params = {
        'message': '',
        'title': 'Traffic: Chrome Infra Monitoring Proxy',
        'xsrf_token': self._handler.generate_xsrf_token(),
    }
    data = common.TrafficSplit.get_or_insert(common.TRAFFIC_SPLIT_KEY)
    config = common.ConfigData.get_or_insert(common.CONFIG_DATA_KEY)
    params.update(data.to_dict())
    params.update({'secondary_endpoint_load': config.secondary_endpoint_load})
    failed_fields = []
    for field in data.to_dict().iterkeys():
      if not self.request.get(field):
        continue
      try:
        logging.info('set_traffic.post: %s = %r',
                     field, self.request.get(field))
        setattr(data, field, int(self.request.get(field)))
      except ValueError:
        failed_fields.append(field)

    field = 'secondary_endpoint_load'
    try:
      logging.info('set_traffic.post: %s = %r',
                   field, self.request.get(field))
      updateConfig(config, field, self.request.get(field))
    except ValueError:
      failed_fields.append(field)

    if failed_fields:
      params['message'] += 'Failed to update %s, please try again.' % (
        ', '.join(failed_fields))
    else:
      data.put()
      config.put()
      params.update(data.to_dict())
      params.update({'secondary_endpoint_load': config.secondary_endpoint_load})
      params['message'] = 'Updated traffic split configuration.'
      logging.info('Updated traffic split: %r', data.to_dict())
    self.render_response('set_traffic.html', **params)


commands = {
  '': AdminPage,
  'set-credentials': SetCredentials,
  'set-traffic': SetTraffic,
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
