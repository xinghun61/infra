# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Entry point for 'default' module that serves UI pages and Endpoints APIs."""

import endpoints
import os
import sys
import webapp2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'components', 'third_party'))

from components import ereporter2
from components import utils
from components import auth

import cas


class MainHandler(webapp2.RequestHandler):
  def get(self):
    self.response.write('Nothing to see here')


class WarmupHandler(webapp2.RequestHandler):
  def get(self):
    auth.warmup()
    self.response.write('ok')


def create_html_app():
  """Returns WSGI app that serves HTML pages."""
  routes = [
    webapp2.Route(r'/', MainHandler),
    webapp2.Route(r'/_ah/warmup', WarmupHandler),
  ]
  routes.extend(ereporter2.get_frontend_routes())
  return webapp2.WSGIApplication(routes, debug=utils.is_local_dev_server())


def create_endpoints_app():
  """Returns WSGI app that serves cloud endpoints requests."""
  return endpoints.api_server([cas.CASServiceApi])


def initialize():
  """Bootstraps the global state and creates WSGI applications."""
  # Collect and send exception reports.
  ereporter2.register_formatter()
  ereporter2.configure()
  return create_html_app(), create_endpoints_app()


# Make apps usable from app.yaml.
html_app, apis_app = initialize()
