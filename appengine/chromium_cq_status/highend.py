# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from handlers.login import Login
from handlers.query import Query
from handlers.stats_query import StatsQuery
from handlers.update_stats import UpdateStats

handlers = [
  (r'/background/update-stats', UpdateStats),
  (r'/login', Login),
  (r'/query(/.*)?', Query),
  (r'/stats/query', StatsQuery),
]

app = webapp2.WSGIApplication(handlers, debug=True)
