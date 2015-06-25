# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import random
import os
import sys
import time
import urllib
import webapp2

from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import app_identity

import common
import handler_utils
from components import auth
from components import net
from components import utils

VM_MODULES = ['vm1', 'vm2', 'vm3']


class NoBackendException(Exception):
  pass


class LoadBalancer(object):
  """Balance the load among VM modules.

  TODO(sergeyberezin): take into account health checks on the
  corresponding NAT boxes. Specifically, fetch the health status
  from the datastore in __init__(), and update it periodically as needed.
  """
  def __init__(self):
    pass

  @staticmethod
  def biased_choice(items):
    """Randomly select an item biased by its weight.

    Args:
      items (dict): map of names to weights (non-negative numbers).
        The bigger the weight, the higher is the chance of selecting this item.
    """
    # Line up the items on a single line as intervals, and randomly
    # pick a point on the line.
    thresholds = []
    total_weight = 0.0
    for name, weight in items.iteritems():
      thresholds.append((name, total_weight))
      total_weight += weight
    thresholds.reverse()
    choice = random.uniform(0.0, total_weight)
    for name, threshold in thresholds:
      if choice >= threshold:
        return name

  def choose_module(self):
    """Select a module to send the data to."""
    # TODO(sergeyberezin): perform health checks for the corresponding
    # NAT boxes and drain modules appropriately.
    return self.biased_choice(common.TrafficSplit.get_or_insert(
        common.TRAFFIC_SPLIT_KEY).to_dict())


def _get_config_data():
  data_entity = common.ConfigData.get_by_id(common.CONFIG_DATA_KEY)
  if not data_entity:
    return None
  return data_entity


def _get_credentials(credentials):
  """Obtain Aquisition API credentials as Credentials object."""
  if not all((credentials.client_email, credentials.private_key,
              credentials.private_key_id)):
    return None

  return auth.ServiceAccountKey(
      client_email=credentials.client_email,
      private_key=credentials.private_key,
      private_key_id=credentials.private_key_id)


class AdminError(Exception):
  pass


def forward_data(data, ip):
  """Forwards the raw data to the backend.

  The request contains all the required headers, incliding a special
  Endpoint-Url header with the endpoint URL, and the correct
  Authorization: header for that endpoint.

  Args:
    data (str): raw binary data to forward.
    ip (str):   the IP address of the data source (used for traffic split).

  Raises:
    AdminError when endpoint data is not entered in the admin console.
  """
  lb = LoadBalancer()
  module_name = lb.choose_module()
  logging.info('Forwarding request to module: %s', module_name)
  hostname = app_identity.get_default_version_hostname()
  if utils.is_local_dev_server():
    protocol = 'http'
    hostname = 'localhost:808%s' % module_name[-1]
  else:
    protocol = 'https'

  config_data = _get_config_data()
  if not config_data:
    raise AdminError('Endpoints are not defined')

  # Make the traffic split deterministic in the source IP.

  # TODO(sergeyberezin): make it truly random. Most of our sources
  # are behind NAT boxes, and appear as the same IP.
  random_state = random.getstate()
  random.seed(ip)
  if random.uniform(0, 100) < config_data.secondary_endpoint_load:
    endpoint = config_data.secondary_endpoint
  else:
    endpoint = config_data.primary_endpoint
  random.setstate(random_state)

  url = '%s://%s/%s' % (protocol, hostname, module_name)
  service_account_key = _get_credentials(endpoint.credentials)
  headers = {
      common.ENDPOINT_URL_HEADER: endpoint.url,
      'Content-Type': 'application/x-protobuf',
  }
  headers.update(endpoint.headers)
  net.request(
      url=url,
      method='POST',
      payload=data,
      headers=headers,
      scopes=endpoint.scopes,
      service_account_key=service_account_key)


class MonacqHandler(auth.AuthenticatingHandler):

  @auth.require(lambda: auth.is_group_member(
      'service-account-monitoring-proxy'))
  def post(self):
    try:
      forward_data(self.request.body, self.request.remote_addr)
    except AdminError as e:
      logging.error('%s; please visit https://%s/admin/',
                    e, app_identity.get_default_version_hostname())
      self.abort(500)


class MainHandler(handler_utils.BaseAuthHandler):
  @auth.public
  def get(self):
    self.render_response('main.html', title='Chrome Infra Monitoring Proxy')


def create_app():
  logging.basicConfig(level=logging.DEBUG)
  if utils.is_local_dev_server():
    handler_utils.init_local_dev_server()

  main_handlers = [
      (r'/', MainHandler),
      (r'/monacq', MonacqHandler),
  ]

  return webapp2.WSGIApplication(main_handlers, debug=True)
