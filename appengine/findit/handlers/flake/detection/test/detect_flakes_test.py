# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import webapp2

from google.appengine.api import app_identity

from gae_libs.handlers.base_handler import BaseHandler
from handlers.flake.detection import detect_flakes
from waterfall.test.wf_testcase import WaterfallTestCase
from services.flake_detection import detect_cq_false_rejection_flakes


class DetectCQFalseRejectionFlakesCronJobTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
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
  app_module = webapp2.WSGIApplication(
      [
          ('/flake/detection/detect-cq-false-rejection-flakes',
           detect_flakes.DetectCQFalseRejectionFlakes),
      ],
      debug=True)

  @mock.patch.object(
      app_identity, 'get_application_id', return_value='findit-for-me-staging')
  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  @mock.patch.object(detect_cq_false_rejection_flakes, 'QueryAndStoreFlakes')
  def testDetectionIsTriggeredOnStaging(self, mocked_query_and_store_flakes,
                                        mocked_is_request_from_appself, _):
    response = self.test_app.get(
        '/flake/detection/detect-cq-false-rejection-flakes')
    self.assertEqual(200, response.status_int)
    self.assertTrue(mocked_query_and_store_flakes.called)
    self.assertTrue(mocked_is_request_from_appself.called)

  @mock.patch.object(
      app_identity, 'get_application_id', return_value='findit-for-me')
  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  @mock.patch.object(detect_cq_false_rejection_flakes, 'QueryAndStoreFlakes')
  def testDetectionIsNotTriggeredOnProduction(
      self, mocked_query_and_store_flakes, mocked_is_request_from_appself, _):
    response = self.test_app.get(
        '/flake/detection/detect-cq-false-rejection-flakes')
    self.assertEqual(200, response.status_int)
    self.assertFalse(mocked_query_and_store_flakes.called)
    self.assertTrue(mocked_is_request_from_appself.called)
