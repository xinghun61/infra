# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import random
import os
import sys
import time
import urllib2
import webapp2

from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import app_identity, taskqueue

import common
from components import auth

VM_MODULES = ['vm1', 'vm2', 'vm3']


def require_group_membership(group_name):
  """Authenticating decorator for handler methods.

  Requires the user to be part of group in production, and
  skips authorization for dev appserver.
  """
  if common.is_development_server():
    auth_decorator = auth.public
  else:
    auth_decorator = auth.require( # pragma: no branch
        lambda: auth.is_group_member(group_name))

  def decorator(fn):
    return auth_decorator(fn)
  return decorator


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

  def choose_module(self):
    """Select a module to send the data to."""
    # TODO(sergeyberezin) Implement load percentages for modules, for
    # draining / canary / live rolling updates.
    # TODO(sergeyberezin): perform health checks for the corresponding
    # NAT boxes and drain modules appropriately.
    return random.choice(VM_MODULES)


def forward_data(data):
  """Forwards the raw data to the backend."""
  # Task queue should work correctly both in dev and prod server.
  lb = LoadBalancer()
  module_name = lb.choose_module()
  logging.info('Forwarding request to module: %s', module_name)
  hostname = app_identity.get_default_version_hostname()
  if common.is_development_server():
    protocol = 'http'
  else:
    protocol = 'https'
  url = '%s://%s/%s' % (protocol, hostname, module_name)
  request = urllib2.Request(url, data)
  urllib2.urlopen(request)


class MonacqHandler(auth.AuthenticatingHandler):
  # Disable XSRF in local dev appserver; otherwise requests will fail.
  if common.is_development_server():
    xsrf_token_enforce_on = []  # pragma: no cover

  @require_group_membership('service-account-monitoring-proxy')
  def post(self):
    forward_data(self.request.body)


class MainHandler(common.BaseHandler):
  def get(self):
    self.render_response('main.html', title='Chrome Infra Monitoring Proxy')


logging.basicConfig(level=logging.DEBUG)

main_handlers = [
    (r'/', MainHandler),
    (r'/monacq', MonacqHandler),
]

app = webapp2.WSGIApplication(main_handlers, debug=True)
