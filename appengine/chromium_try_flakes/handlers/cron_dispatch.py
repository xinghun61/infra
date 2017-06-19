# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from google.appengine.api import users

from status import cq_status
from handlers import lemur_test

commands = {
  'fetch_cq_status': cq_status.fetch_cq_status,
  'update_histograms': cq_status.update_histograms,
  'update_issue_tracker': cq_status.update_issue_tracker,
  'update_stale_issues': cq_status.update_stale_issues,
  'update_flake_hour_counter': cq_status.update_flake_hour_counter,
  'update_flake_day_counter': cq_status.update_flake_day_counter,
  'update_flake_week_counter': cq_status.update_flake_week_counter,
  'update_flake_month_counter': cq_status.update_flake_month_counter,
  'delete_old_flake_occurrences': cq_status.delete_old_flake_occurrences,
  'process_new_flakes': lemur_test.process_new_flakes,
}

class CronDispatch(webapp2.RequestHandler):
  def get(self, job):
    commands[job]()
