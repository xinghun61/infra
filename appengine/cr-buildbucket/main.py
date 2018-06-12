# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from components import endpoints_webapp2
from components import ereporter2
from components import utils
import gae_ts_mon
import webapp2

import handlers
import metrics
import swarming


def create_frontend_app():  # pragma: no cover
  """Returns WSGI app for frontend."""
  app = webapp2.WSGIApplication(
      handlers.get_frontend_routes(), debug=utils.is_local_dev_server())
  gae_ts_mon.initialize(app)
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
