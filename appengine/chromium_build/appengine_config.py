# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

ENABLE_APPSTATS = False

# Make webapp.template use django 1.2.  Quells default django warning.
from google.appengine.dist import use_library
use_library('django', '1.2')

if ENABLE_APPSTATS:
  def webapp_add_wsgi_middleware(app):
    from google.appengine.ext.appstats import recording
    app = recording.appstats_wsgi_middleware(app)
    return app
