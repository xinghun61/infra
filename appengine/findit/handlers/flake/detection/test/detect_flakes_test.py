# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import urllib2
import webapp2

from gae_libs.handlers.base_handler import BaseHandler
from handlers.flake.detection import detect_flakes
from model.flake.flake_type import FlakeType
from model.flake.flake_type import FLAKE_TYPE_DESCRIPTIONS
from services.flake_detection import detect_flake_occurrences
from services.flake_detection.detect_flake_occurrences import (
    DetectFlakesFromFlakyCQBuildParam)
from waterfall.test.wf_testcase import WaterfallTestCase


class DetectFlakesCronJobTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/flake/detection/cron/detect-flakes',
           detect_flakes.DetectFlakesCronJob),
      ],
      debug=True,
  )

  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  def testTaskAddedToQueue(self, mocked_is_request_from_appself):
    response = self.test_app.get('/flake/detection/cron/detect-flakes')
    self.assertEqual(200, response.status_int)
    response = self.test_app.get('/flake/detection/cron/detect-flakes')
    self.assertEqual(200, response.status_int)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        queue_names='flake-detection-queue')
    self.assertEqual(6, len(tasks))
    self.assertTrue(mocked_is_request_from_appself.called)


class FlakeDetectionTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/flake/detection/task/detect-flakes', detect_flakes.FlakeDetection),
      ],
      debug=True,
  )

  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  @mock.patch.object(detect_flake_occurrences, 'QueryAndStoreHiddenFlakes')
  @mock.patch.object(detect_flake_occurrences, 'QueryAndStoreNonHiddenFlakes')
  def testFlakesDetectionNoType(self, mock_detect, mock_detect_hidden, _):
    response = self.test_app.get(
        '/flake/detection/task/detect-flakes', status=404)
    self.assertEqual(404, response.status_int)
    self.assertFalse(mock_detect.called)
    self.assertFalse(mock_detect_hidden.called)

  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  @mock.patch.object(detect_flake_occurrences, 'QueryAndStoreHiddenFlakes')
  @mock.patch.object(detect_flake_occurrences, 'QueryAndStoreNonHiddenFlakes')
  def testFlakesDetectionNonHidden(self, mock_detect, mock_detect_hidden, _):
    response = self.test_app.get(
        '/flake/detection/task/detect-flakes?flake_type={}'.format(
            urllib2.quote(
                FLAKE_TYPE_DESCRIPTIONS[FlakeType.CQ_FALSE_REJECTION])),
        status=200)
    self.assertEqual(200, response.status_int)

    mock_detect.assert_called_once_with(FlakeType.CQ_FALSE_REJECTION)
    self.assertFalse(mock_detect_hidden.called)

  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  @mock.patch.object(
      detect_flake_occurrences, 'QueryAndStoreHiddenFlakes', return_value=[])
  @mock.patch.object(detect_flake_occurrences, 'QueryAndStoreNonHiddenFlakes')
  def testFlakesDetectionHidden(self, mock_detect_non_hidden,
                                mock_detect_hidden, _):
    response = self.test_app.get(
        '/flake/detection/task/detect-flakes?flake_type={}'.format(
            urllib2.quote(FLAKE_TYPE_DESCRIPTIONS[FlakeType.CQ_HIDDEN_FLAKE])),
        status=200)
    self.assertEqual(200, response.status_int)

    self.assertFalse(mock_detect_non_hidden.called)
    self.assertTrue(mock_detect_hidden.called)


class DetectFlakesFromFlakyCQBuildTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/flake/detection/task/detect-flakes-from-build',
           detect_flakes.DetectFlakesFromFlakyCQBuild),
      ],
      debug=True,
  )

  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  @mock.patch.object(detect_flake_occurrences, 'ProcessBuildForFlakes')
  def testFlakesDetected(self, mock_detect, _):
    flake_type = FlakeType.CQ_FALSE_REJECTION
    params = DetectFlakesFromFlakyCQBuildParam(
        build_id=123, flake_type_desc=FLAKE_TYPE_DESCRIPTIONS[flake_type])
    response = self.test_app.post(
        '/flake/detection/task/detect-flakes-from-build',
        params=json.dumps(params.ToSerializable()),
        headers={'X-AppEngine-QueueName': 'task_queue'})
    self.assertEqual(200, response.status_int)

    mock_detect.assert_called_once_with(params)
