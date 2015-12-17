# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
import google

google.__path__.insert(
  0, os.path.join(APP_DIR, 'components', 'third_party', 'protobuf', 'google'))

from components import config
from components import ereporter2
from components import utils
import endpoints
import gae_ts_mon
import webapp2

import api
import handlers
import swarming


def create_html_app():  # pragma: no cover
  """Returns WSGI app that serves HTML pages."""
  app = webapp2.WSGIApplication(
    handlers.get_frontend_routes(), debug=utils.is_local_dev_server())
  gae_ts_mon.initialize(app)
  return app


def create_endpoints_app():  # pragma: no cover
  """Returns WSGI app that serves cloud endpoints requests."""
  return endpoints.api_server([api.BuildBucketApi, config.ConfigApi])


def create_backend_app():  # pragma: no cover
  """Returns WSGI app for backend."""
  routes = handlers.get_backend_routes() + swarming.get_routes()
  app = webapp2.WSGIApplication(routes, debug=utils.is_local_dev_server())
  gae_ts_mon.initialize(app)
  return app


def initialize():  # pragma: no cover
  """Bootstraps the global state and creates WSGI applications."""
  ereporter2.register_formatter()
  return create_html_app(), create_endpoints_app(), create_backend_app()
