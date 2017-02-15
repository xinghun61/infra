# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

import base64
import json
import logging
import os
import time
import urllib
import webapp2

from google import protobuf
from google.appengine.api import app_identity
from google.appengine.api import urlfetch
from google.appengine.ext import db

from infra_libs import ts_mon

import settings
from framework import framework_constants
from proto import api_clients_config_pb2


CONFIG_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    'testing', 'api_clients.cfg')
MONORAIL_CONFIG_SET = urllib.quote(
    'services/%s' % app_identity.get_application_id(), safe='')
LUCI_CONFIG_URL = (
    'https://luci-config.appspot.com/_ah/api/config/v1/config_sets'
    '/%s/config/api_clients.cfg') % MONORAIL_CONFIG_SET


client_config_svc = None
service_account_map = None
qpm_dict = None


class ClientConfig(db.Model):
  configs = db.TextProperty()


# Note: The cron job must have hit the servlet before this will work.
class LoadApiClientConfigs(webapp2.RequestHandler):

  config_loads = ts_mon.CounterMetric(
      'monorail/client_config_svc/loads',
      'Results of fetches from luci-config.',
      [ts_mon.BooleanField('success'), ts_mon.StringField('type')])

  def get(self):
    authorization_token, _ = app_identity.get_access_token(
      framework_constants.OAUTH_SCOPE)
    response = urlfetch.fetch(
      LUCI_CONFIG_URL,
      method=urlfetch.GET,
      follow_redirects=False,
      headers={'Content-Type': 'application/json; charset=UTF-8',
              'Authorization': 'Bearer ' + authorization_token})

    if response.status_code != 200:
      logging.error('Invalid response from luci-config: %r', response)
      self.config_loads.increment({'success': False, 'type': 'luci-cfg-error'})
      self.abort(500, 'Invalid response from luci-config')

    try:
      content_text = self._process_response(response)
    except Exception as e:
      self.abort(500, str(e))

    logging.info('luci-config content decoded: %r.', content_text)
    configs = ClientConfig(configs=content_text,
                            key_name='api_client_configs')
    configs.put()
    self.config_loads.increment({'success': True, 'type': 'success'})

  def _process_response(self, response):
    try:
      content = json.loads(response.content)
    except ValueError:
      logging.error('Response was not JSON: %r', response.content)
      self.config_loads.increment({'success': False, 'type': 'json-load-error'})
      raise

    try:
      config_content = content['content']
    except KeyError:
      logging.error('JSON contained no content: %r', content)
      self.config_loads.increment({'success': False, 'type': 'json-key-error'})
      raise

    try:
      content_text = base64.b64decode(config_content)
    except TypeError:
      logging.error('Content was not b64: %r', config_content)
      self.config_loads.increment({'success': False,
                                   'type': 'b64-decode-error'})
      raise

    try:
      cfg = api_clients_config_pb2.ClientCfg()
      protobuf.text_format.Merge(content_text, cfg)
    except:
      logging.error('Content was not a valid ClientCfg proto: %r', content_text)
      self.config_loads.increment({'success': False,
                                   'type': 'proto-load-error'})
      raise

    return content_text


class ClientConfigService(object):
  """The persistence layer for client config data."""

  # One hour
  EXPIRES_IN = 3600

  def __init__(self):
    self.client_configs = None
    self.load_time = 0

  def GetConfigs(self, use_cache=True, cur_time=None):
    """Read client configs."""

    cur_time = cur_time or int(time.time())
    force_load = False
    if not self.client_configs:
      force_load = True
    elif not use_cache:
      force_load = True
    elif cur_time - self.load_time > self.EXPIRES_IN:
      force_load = True

    if force_load:
      if settings.dev_mode or settings.unit_test_mode:
        self._ReadFromFilesystem()
      else:
        self._ReadFromDatastore()

    return self.client_configs

  def _ReadFromFilesystem(self):
    try:
      with open(CONFIG_FILE_PATH, 'r') as f:
        content_text = f.read()
      logging.info('Read client configs from local file.')
      cfg = api_clients_config_pb2.ClientCfg()
      protobuf.text_format.Merge(content_text, cfg)
      self.client_configs = cfg
      self.load_time = int(time.time())
    except Exception as e:
      logging.exception('Failed to read client configs: %s', e)

  def _ReadFromDatastore(self):
    entity = ClientConfig.get_by_key_name('api_client_configs')
    if entity:
      cfg = api_clients_config_pb2.ClientCfg()
      protobuf.text_format.Merge(entity.configs, cfg)
      self.client_configs = cfg
      self.load_time = int(time.time())
    else:
      logging.error('Failed to get api client configs from datastore.')

  def GetClientIDEmails(self):
    """Get client IDs and Emails."""
    self.GetConfigs(use_cache=True)
    client_ids = [c.client_id for c in self.client_configs.clients]
    client_emails = [c.client_email for c in self.client_configs.clients]
    return client_ids, client_emails

  def GetDisplayNames(self):
    """Get client display names."""
    self.GetConfigs(use_cache=True)
    names_dict = {}
    for client in self.client_configs.clients:
      if client.display_name:
        names_dict[client.client_email] = client.display_name
    return names_dict

  def GetQPM(self):
    """Get client qpm limit."""
    self.GetConfigs(use_cache=True)
    qpm_map = {}
    for client in self.client_configs.clients:
      if client.display_name:
        qpm_map[client.client_email] = client.qpm_limit
    return qpm_map


def GetClientConfigSvc():
  global client_config_svc
  if client_config_svc is None:
    client_config_svc = ClientConfigService()
  return client_config_svc


def GetServiceAccountMap():
  global service_account_map
  if service_account_map is None:
    service_account_map = GetClientConfigSvc().GetDisplayNames()
  return service_account_map


def GetQPMDict():
  global qpm_dict
  if qpm_dict is None:
    qpm_dict = GetClientConfigSvc().GetQPM()
  return qpm_dict
