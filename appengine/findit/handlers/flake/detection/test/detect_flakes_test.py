# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import webapp2

from gae_libs.handlers.base_handler import BaseHandler
from handlers.flake.detection import detect_flakes
from model.flake.flake_type import FlakeType
from services import flake_issue_util
from services.flake_detection import detect_flake_occurrences
from waterfall.test.wf_testcase import WaterfallTestCase


class DetectCQFalseRejectionFlakesCronJobTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/flake/detection/cron/detect-cq-false-rejection-flakes',
       detect_flakes.DetectCQFalseRejectionFlakesCronJob),
  ],
                                       debug=True)

  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  def testTaskAddedToQueue(self, mocked_is_request_from_appself):
    response = self.test_app.get(
        '/flake/detection/cron/detect-cq-false-rejection-flakes')
    self.assertEqual(200, response.status_int)
    response = self.test_app.get(
        '/flake/detection/cron/detect-cq-false-rejection-flakes')
    self.assertEqual(200, response.status_int)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        queue_names='flake-detection-queue')
    self.assertEqual(2, len(tasks))
    self.assertTrue(mocked_is_request_from_appself.called)


class DetectCQFalseRejectionFlakesTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/flake/detection/task/detect-cq-false-rejection-flakes',
       detect_flakes.DetectCQFalseRejectionFlakes),
  ],
                                       debug=True)

  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  @mock.patch.object(flake_issue_util, 'ReportFlakesToFlakeAnalyzer')
  @mock.patch.object(flake_issue_util, 'ReportFlakesToMonorail')
  @mock.patch.object(flake_issue_util, 'GetFlakesWithEnoughOccurrences')
  @mock.patch.object(detect_flake_occurrences, 'QueryAndStoreFlakes')
  def testFlakesDetected(self, mock_detect, mock_get_flakes, mock_bug,
                         mock_analysis, _):
    mock_get_flakes.return_value = []
    response = self.test_app.get(
        '/flake/detection/task/detect-cq-false-rejection-flakes', status=200)
    self.assertEqual(200, response.status_int)

    mock_detect.assert_has_calls([
        mock.call(FlakeType.CQ_FALSE_REJECTION),
        mock.call(FlakeType.RETRY_WITH_PATCH)
    ])
    mock_bug.assert_called_once_with([])
    mock_analysis.assert_called_once_with([])
