# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Sets up WSGI apps that serve UI pages."""

import endpoints
import os
import sys
import webapp2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'components', 'third_party'))

from components import ereporter2
from components import utils

import feebas  # Buildbot Endpoints
# import milotic  # LUCI Endpoints
import log2milo


main_file = (
    'html/main.html' if utils.is_local_dev_server()
    else 'vulcanized_main.html')
path = os.path.join(os.path.dirname(__file__), main_file)

f = open(path, 'rb')
main = f.read()
f.close()


class MainPage(webapp2.RequestHandler):
  def get(self):
    self.response.headers['Strict-Transport-Security'] = (
        'max-age=10886400; includeSubDomains')
    self.response.headers['Content-Type'] = 'text/html'
    self.response.out.write(main)


def create_html_app():
  """Returns WSGI app that serves HTML pages."""
  routes = []
  routes.extend(ereporter2.get_frontend_routes())
  routes.extend(ereporter2.get_backend_routes())
  routes.append((r'.*', MainPage))
  return webapp2.WSGIApplication(routes, debug=utils.is_local_dev_server())


def create_endpoints_app():
  """Returns WSGI app that serves cloud endpoints requests."""
  apis = [feebas.FeebasApi, log2milo.LogApi]
  return endpoints.api_server(apis, restricted=not utils.is_local_dev_server())


def initialize():
  """Bootstraps the global state and creates WSGI applications."""
  ereporter2.register_formatter()
  ereporter2.configure()
  return create_html_app(), create_endpoints_app()
