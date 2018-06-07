# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from components import config
from components import endpoints_webapp2
from components import ereporter2
from components import utils
import gae_ts_mon
import webapp2

import api
import handlers
import metrics
import swarming
from swarming import swarmbucket_api


def create_frontend_app():  # pragma: no cover
  """Returns WSGI app for frontend."""
  # Currently endpoints_webapp2.api_server returns a list of routes, so we
  # could create a webapp2.WSGIApplication with (API routes + frontend routes).
  # In the future, it will return a webapp2.WSGIApplication directly, to which
  # we will have to append frontend routes.
  app = webapp2.WSGIApplication(endpoints_webapp2.api_server(
      [api.BuildbucketApi, swarmbucket_api.SwarmbucketApi, config.ConfigApi],
      base_path='/_ah/api'), debug=utils.is_local_dev_server())
  for route in handlers.get_frontend_routes():
    app.router.add(route)
  return app


def create_backend_app():  # pragma: no cover
  """Returns WSGI app for backend."""
  routes = handlers.get_backend_routes() + swarming.get_backend_routes()
  app = webapp2.WSGIApplication(routes, debug=utils.is_local_dev_server())
  gae_ts_mon.initialize(app, cron_module='backend')
  gae_ts_mon.register_global_metrics(metrics.GLOBAL_METRICS)
  gae_ts_mon.register_global_metrics_callback('buildbucket_global',
                                              metrics.update_global_metrics)
  return app


def initialize():  # pragma: no cover
  """Bootstraps the global state and creates WSGI applications."""
  ereporter2.register_formatter()
  return create_frontend_app(), create_backend_app()
