# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from monorail_api import IssueTrackerAPI

from common import monitoring
from gae_libs import appengine_util
from gae_libs.handlers.base_handler import BaseHandler, Permission


METRIC_TO_CLIENT_TO_QUERY = {
    'wrong_cls': {
        'clusterfuzz':('Test=Predator-Auto-Components '
                       'Test=Predator-Wrong-Components opened>today-1'),
    },
    'wrong_components': {
        'clusterfuzz': ('Test=Predator-Auto-Owner Test=Predator-Wrong-CLs '
                        'opened>today-1')
    }
}


class UpdateMonorailMetrics(BaseHandler):
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    """Update the metrics based on monorail bugs."""
    issue_tracker_api = IssueTrackerAPI(
        'chromium', use_staging=appengine_util.IsStaging())

    for metric, client_to_query in METRIC_TO_CLIENT_TO_QUERY.iteritems():
      for client, query in client_to_query.iteritems():
        issues = issue_tracker_api.getIssues(query)
        logging.info('Fetch %d issues for client %s using query %s',
                     len(issues), client, query)
        getattr(monitoring, metric).set(len(issues),
                                        fields={'client_id': client})
