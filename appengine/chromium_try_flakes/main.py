# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gae_ts_mon
import gae_event_mon
import webapp2

from google.appengine.api import app_identity
from handlers import flake_issues
from handlers import lemur_test
from handlers.all_flake_occurrences import AllFlakeOccurrences
from handlers.cron_dispatch import CronDispatch
from handlers.index import Index
from handlers.post_comment import PostComment
from handlers.search import Search

handlers = [
  (r'/', Index),
  (r'/post_comment', PostComment),
  (r'/all_flake_occurrences', AllFlakeOccurrences),
  (r'/search', Search),
  (r'/cron/(.*)', CronDispatch),
  (r'/issues/process/(.*)', flake_issues.ProcessIssue),
  (r'/issues/update-if-stale/(.*)', flake_issues.UpdateIfStaleIssue),
  (r'/issues/create_flaky_run', flake_issues.CreateFlakyRun),
  (r'/override_issue_id', flake_issues.OverrideIssueId),
  (r'/lemur_test', lemur_test.ProcessNewFlakes),
  (r'/lemur_update_cache', lemur_test.OnlyUpdateCache),
  (r'/lemur_process_flakes', lemur_test.OnlyProcessFlakes),
]

def is_monitoring_enabled():
  return not app_identity.get_application_id().endswith('-staging')

app = webapp2.WSGIApplication(handlers, debug=True)
gae_ts_mon.initialize(app, is_enabled_fn=is_monitoring_enabled)
gae_event_mon.initialize('flakiness_pipeline')
