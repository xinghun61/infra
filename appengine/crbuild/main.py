# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

from components import utils
from components import ereporter2
import endpoints
import webapp2

import buildbucket

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(APP_DIR, 'third_party'))

# TODO(nodir): include ui and tasks
handlers = []


def create_html_app():  # pragma: no cover
  """Returns WSGI app that serves HTML pages."""
  routes = [
  ]
  return webapp2.WSGIApplication(routes, debug=utils.is_local_dev_server())


def create_endpoints_app():  # pragma: no cover
  """Returns WSGI app that serves cloud endpoints requests."""
  apis = [
      buildbucket.BuildBucketApi,
  ]
  return endpoints.api_server(apis)


def create_backend_app():  # pragma: no cover
  """Returns WSGI app for backend."""
  routes = []
  routes += buildbucket.get_backend_routes()
  return webapp2.WSGIApplication(routes, debug=utils.is_local_dev_server())


def initialize():  # pragma: no cover
  """Bootstraps the global state and creates WSGI applications."""
  ereporter2.register_formatter()
  return create_html_app(), create_endpoints_app(), create_backend_app()
