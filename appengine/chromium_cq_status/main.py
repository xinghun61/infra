# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gae_ts_mon
import webapp2

from handlers.admin_dispatch import AdminDispatch
from handlers.index import Index
from handlers.patch_status import PatchStatus, PatchStatusV2
from handlers.patch_summary import PatchSummary, PatchSummaryV2
from handlers.post import Post
from handlers.recent import Recent

handlers = [
  (r'/', Index),
  (r'/recent', Recent),
  (r'/admin/(.*)', AdminDispatch),
  (r'/patchset/(.*)/(.*)', PatchStatus),  # Legacy URL for old links.
  (r'/patch-status/(.*)/(.*)', PatchStatus),
  (r'/patch-summary/(.*)/(.*)', PatchSummary),
  (r'/v2/patch-status/(.*)/(.*)/(.*)', PatchStatusV2),
  (r'/v2/patch-summary/(.*)/(.*)/(.*)', PatchSummaryV2),
  (r'/post', Post),
]

app = webapp2.WSGIApplication(handlers, debug=True)
gae_ts_mon.initialize(app)
