# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from appengine_module.chromium_cq_status.handlers.login import Login
from appengine_module.chromium_cq_status.handlers.query import Query
from appengine_module.chromium_cq_status.handlers.stats_query import StatsQuery
from appengine_module.chromium_cq_status.handlers.update_stats import UpdateStats  # pylint: disable=C0301

handlers = [
  (r'/background/update-stats', UpdateStats),
  (r'/login', Login),
  (r'/query(/.*)?', Query),
  (r'/stats/query', StatsQuery),
]

app = webapp2.WSGIApplication(handlers, debug=True)
