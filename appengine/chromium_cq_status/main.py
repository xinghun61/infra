# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from handlers.admin_dispatch import AdminDispatch
from handlers.index import Index
from handlers.post import Post
from handlers.query import Query
from handlers.stats_viewer import StatsViewer
from handlers.stats_query import StatsQuery

handlers = [
  (r'/', Index),
  (r'/admin/(.*)', AdminDispatch),
  (r'/post', Post),
  (r'/query(/.*)?', Query),
  (r'/stats/query', StatsQuery),
  (r'/stats/(.*)/(daily|weekly)', StatsViewer),
]

app = webapp2.WSGIApplication(handlers, debug=True)
