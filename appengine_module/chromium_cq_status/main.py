# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from appengine_module.chromium_cq_status.handlers.admin_dispatch import AdminDispatch  # pylint: disable=C0301
from appengine_module.chromium_cq_status.handlers.index import Index
from appengine_module.chromium_cq_status.handlers.post import Post
from appengine_module.chromium_cq_status.handlers.stats_viewer import StatsViewer  # pylint: disable=C0301
from appengine_module.chromium_cq_status.handlers.stats_query import StatsQuery

handlers = [
  (r'/', Index),
  (r'/admin/(.*)', AdminDispatch),
  (r'/post', Post),
  (r'/stats/query', StatsQuery),
  (r'/stats/(.*)/(daily|weekly)', StatsViewer),
]

app = webapp2.WSGIApplication(handlers, debug=True)
