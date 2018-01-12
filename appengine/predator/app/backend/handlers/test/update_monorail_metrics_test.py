# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import webapp2

from google.appengine.api import users

from backend.handlers.update_monorail_metrics import UpdateMonorailMetrics
from common import monitoring
from gae_libs.testcase import TestCase


class UpdateMonorailMetricsTest(TestCase):
  """Tests utility functions and ``UpdateMonorailMetrics`` handler."""
  app_module = webapp2.WSGIApplication([
      ('/process/update-monorail-metrics', UpdateMonorailMetrics),
  ], debug=True)

  @mock.patch('common.monitoring.wrong_components')
  @mock.patch('common.monitoring.wrong_cls')
  @mock.patch('backend.handlers.update_monorail_metrics.IssueTrackerAPI')
  def testUpdateMetrics(self, mock_issue_tracker_api, mock_wrong_cls,
                        mock_wrong_components):
    mock_issue_tracker_api.return_value.getIssues.return_value = [None, None]
    response = self.test_app.get('/process/update-monorail-metrics',
                                 headers={'X-AppEngine-Cron': 'true'})

    self.assertEqual(response.status_int, 200)
    mock_wrong_cls.set.assert_called_with(
        2, fields={'client_id': 'clusterfuzz'})
    mock_wrong_components.set.assert_called_with(
        2, fields={'client_id': 'clusterfuzz'})
