# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definition of WSGI application for all modules.

WSGI apps are actually instantiated in apps.py.
"""

import endpoints
import hashlib
import logging
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'components', 'third_party'))

import webapp2

from google.appengine.api import memcache

from components import auth
from components import config
from components import ereporter2
from components import utils

import admin
import cas
import cipd


STATIC_DIR = os.path.join(BASE_DIR, 'static')


class MainHandler(webapp2.RequestHandler):
  """Serves index-vulcanized.html or index.html."""

  def get(self):
    if (not utils.is_local_dev_server() or
        os.path.isfile(os.path.join(STATIC_DIR, 'html/index-vulcanized.html'))):
      self.send_static('html/index-vulcanized.html')
    else:
      logging.warning('Serving unvulcanized version of index.html')
      self.send_static('html/index.html')

  def send_static(self, path):
    """Sends static file to client, using etag for cache invalidation."""
    # Does client already have the needed version in cache?
    client_etag = self.request.headers.get('If-None-Match')
    server_etag, content = self.calculate_etag(path)
    if client_etag == server_etag:
      self.response.set_status(304)
      return
    self.response.headers['Etag'] = server_etag
    self.response.write(content or self.read_static(path))

  def calculate_etag(self, path):
    """Calculates the hash of the given static file or grabs it from cache.

    Returns:
      Tuple (etag, the body of the file if it was read)
    """
    version = utils.get_app_version()

    # Tainted versions are frequently overwritten, do not cache static files for
    # too long for them. Same for devserver.
    expiration_sec = 3600
    if '-tainted' in version or utils.is_local_dev_server():
      expiration_sec = 1

    key = '%s:%s' % (version, path)
    value = memcache.get(key, namespace='etag')
    if value:
      return value, None

    body = self.read_static(path)
    value = '"%s"' % hashlib.sha1(body).hexdigest()
    memcache.set(key, value, time=expiration_sec, namespace='etag')
    return value, body

  def read_static(self, path):
    """Reads static file body or raises HTTP 404 if not found."""
    abs_path = os.path.abspath(os.path.join(STATIC_DIR, path))
    assert abs_path.startswith(STATIC_DIR + '/'), abs_path
    try:
      with open(abs_path, 'rb') as f:
        body = f.read()
      # HACK: index.html doesn't expect to be served from the site root.
      # Tweak it to make it work anyway. This code path should never be
      # triggered in prod (since prod always serves vulcanized version).
      if abs_path.endswith('/static/html/index.html'):
        assert utils.is_local_dev_server()
        body = body.replace('../bower_components/', '/static/bower_components/')
        body = body.replace('cipd-app.html', '/static/html/cipd-app.html')
      return body
    except IOError:
      self.abort(404)


def create_endpoints_app():
  """Returns WSGI app that serves cloud endpoints requests."""
  apis = [
    admin.AdminApi,
    auth.AuthService,
    cas.CASServiceApi,
    cipd.PackageRepositoryApi,
    config.ConfigApi,
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
  routes.extend(cipd.get_backend_routes())
  return webapp2.WSGIApplication(routes, debug=utils.is_local_dev_server())


def initialize():
  """Bootstraps the global state and creates WSGI applications."""
  ereporter2.register_formatter()
  return create_endpoints_app(), create_frontend_app(), create_backend_app()
