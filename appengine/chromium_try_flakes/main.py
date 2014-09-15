# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import webapp2

sys.path.append("third_party")

from handlers.cron_dispatch import CronDispatch
from handlers.index import Index
from handlers.post_comment import PostComment
from handlers.all_flake_occurrences import AllFlakeOccurrences
from handlers.search import Search

handlers = [
  (r'/', Index),
  (r'/post_comment', PostComment),
  (r'/all_flake_occurrences', AllFlakeOccurrences),
  (r'/search', Search),
  (r'/cron/(.*)', CronDispatch),
]

app = webapp2.WSGIApplication(handlers, debug=True)
