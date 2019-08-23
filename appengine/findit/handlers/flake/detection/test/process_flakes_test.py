# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import webapp2

from gae_libs.handlers.base_handler import BaseHandler
from handlers.flake.detection import process_flakes
from services import flake_issue_util
from waterfall.test.wf_testcase import WaterfallTestCase


class ProcessFlakesCronJobTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/flake/detection/cron/process-flakes',
           process_flakes.ProcessFlakesCronJob),
      ],
      debug=True,
  )

  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  def testTaskAddedToQueue(self, mocked_is_request_from_appself):
    response = self.test_app.get('/flake/detection/cron/process-flakes')
    self.assertEqual(200, response.status_int)
    response = self.test_app.get('/flake/detection/cron/process-flakes')
    self.assertEqual(200, response.status_int)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        queue_names='flake-detection-queue')
    self.assertEqual(2, len(tasks))
    self.assertTrue(mocked_is_request_from_appself.called)


class FlakeDetectionAndAutoActionTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/flake/detection/task/process-flakes',
           process_flakes.FlakeAutoAction),
      ],
      debug=True,
  )

  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  @mock.patch.object(
      flake_issue_util, 'GetFlakeGroupsForActionsOnBugs', return_value=([], []))
  @mock.patch.object(flake_issue_util, 'ReportFlakesToFlakeAnalyzer')
  @mock.patch.object(flake_issue_util, 'ReportFlakesToMonorail')
  @mock.patch.object(flake_issue_util, 'GetFlakesWithEnoughOccurrences')
  def testFlakesDetected(self, mock_get_flakes, mock_bug, mock_analysis,
                         mock_groups, _):
    mock_get_flakes.return_value = []
    response = self.test_app.get(
        '/flake/detection/task/process-flakes', status=200)
    self.assertEqual(200, response.status_int)

    mock_bug.assert_called_once_with([], [])
    mock_analysis.assert_called_once_with([])
    mock_groups.assert_called_once_with([])
