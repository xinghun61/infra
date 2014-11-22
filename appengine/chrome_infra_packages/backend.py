# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Entry point for 'backend' module that performs offline tasks."""

import os
import sys
import webapp2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'components', 'third_party'))

from components import ereporter2
from components import utils

from cas import impl as cas_impl


def create_application():
  """Bootstraps the global state and creates WSGI application."""
  ereporter2.register_formatter()
  ereporter2.configure()

  routes = []
  routes.extend(ereporter2.get_backend_routes())
  routes.extend(cas_impl.get_backend_routes())
  return webapp2.WSGIApplication(routes, debug=utils.is_local_dev_server())


app = create_application()
