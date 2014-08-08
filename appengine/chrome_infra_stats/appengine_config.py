# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

apptrace_URL_PATTERNS  = ['top50']
apptrace_TRACE_MODULES = ['models.py', 'app.py', 'views.py']


def webapp_add_wsgi_middleware(app):
  from google.appengine.ext.appstats import recording
  app = recording.appstats_wsgi_middleware(app)
  try:
    from apptrace.middleware import apptrace_middleware
    app = apptrace_middleware(app)
  except ImportError:
    pass
  return app
