# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definition of WSGI application for all modules.

WSGI apps are actually instantiated in apps.py.
"""

import endpoints
import os
import sys
import webapp2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'components', 'third_party'))

from components import ereporter2
from components import utils

import admin
import cas


class MainHandler(webapp2.RequestHandler):
  def get(self):
    self.redirect('/_ah/api/explorer')


def create_endpoints_app():
  """Returns WSGI app that serves cloud endpoints requests."""
  apis = [
    admin.AdminApi,
    cas.CASServiceApi,
  ]
  return endpoints.api_server(apis, restricted=not utils.is_local_dev_server())


def create_frontend_app():
  """Returns WSGI app that serves HTML pages."""
  routes = [webapp2.Route(r'/', MainHandler)]
  return webapp2.WSGIApplication(routes, debug=utils.is_local_dev_server())


def create_backend_app():
  """Returns WSGI app that serves task queue and cron handlers."""
  routes = []
  routes.extend(cas.get_backend_routes())
  return webapp2.WSGIApplication(routes, debug=utils.is_local_dev_server())


def initialize():
  """Bootstraps the global state and creates WSGI applications."""
  ereporter2.register_formatter()
  return create_endpoints_app(), create_frontend_app(), create_backend_app()
