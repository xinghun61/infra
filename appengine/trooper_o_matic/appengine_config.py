# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Enable AppStats.

See https://developers.google.com/appengine/docs/python/tools/appstats
"""
from google.appengine.ext.appstats import recording

appstats_SHELL_OK = True


def webapp_add_wsgi_middleware(app):
  app = recording.appstats_wsgi_middleware(app)
  return app
