# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import webapp2

from gae_libs.handlers.base_handler import BaseHandler
from handlers.disabled_tests.detection import detect_test_disablement
from services import disabled_tests
from waterfall.test.wf_testcase import WaterfallTestCase


class DetectTestDisablementCronJobTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/disabled-tests/detection/cron/detect-test-disablement',
       detect_test_disablement.DetectTestDisablementCronJob),
  ],
                                       debug=True)

  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  def testTaskAddedToQueue(self, mocked_is_request_from_appself):
    response = self.test_app.get(
        '/disabled-tests/detection/cron/detect-test-disablement')
    self.assertEqual(200, response.status_int)
    response = self.test_app.get(
        '/disabled-tests/detection/cron/detect-test-disablement')
    self.assertEqual(200, response.status_int)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        queue_names='disabled-test-detection-queue')
    self.assertEqual(2, len(tasks))
    self.assertTrue(mocked_is_request_from_appself.called)


class DisabledTestDetectionTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/disabled-tests/detection/task/detect-test-disablement',
       detect_test_disablement.DisabledTestDetection),
  ],
                                       debug=True)

  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  @mock.patch.object(disabled_tests.detect_disabled_tests,
                     'ProcessQueryForDisabledTests')
  def testDisabledTestsDetected(self, mock_detect, _):
    response = self.test_app.get(
        '/disabled-tests/detection/task/detect-test-disablement', status=200)
    self.assertEqual(1, mock_detect.call_count)
    self.assertEqual(200, response.status_int)
