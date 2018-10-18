# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gae_ts_mon
import webapp2

from handlers.login import Login
from handlers.query import Query

handlers = [
  (r'/login', Login),
  (r'/query(/.*)?', Query),
]

app = webapp2.WSGIApplication(handlers, debug=True)
gae_ts_mon.initialize(app)
