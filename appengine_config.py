# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""AppEngine configuration.

See http://code.google.com/appengine/docs/python/tools/appstats.html for more
details.
"""

import os

# Force use of django 1.2
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from google.appengine.dist import use_library
use_library('django', '1.2')


MIDDLEWARE_CLASSES = (
  'google.appengine.ext.appstats.recording.AppStatsDjangoMiddleware',
)


def webapp_add_wsgi_middleware(app):
  """Adds support for /_ah/stats, callled automatically by run_wsgi_app()."""
  from google.appengine.ext.appstats import recording
  return recording.appstats_wsgi_middleware(app)
