# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import webapp2

from gae_libs.handlers.base_handler import BaseHandler
from handlers.flake.detection import update_flake_counts
from services.flake_detection import update_flake_counts_service
from waterfall.test.wf_testcase import WaterfallTestCase


class UpdateFlakeCountsCronTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/flake/detection/cron/update-flake-counts',
           update_flake_counts.UpdateFlakeCountsCron),
      ],
      debug=True)

  def setUp(self):
    super(UpdateFlakeCountsCronTest, self).setUp()
    self.url = '/flake/detection/cron/update-flake-counts'

  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  def testTaskAddedToQueue(self, mocked_is_request_from_appself):
    response = self.test_app.get(self.url)
    self.assertEqual(200, response.status_int)
    response = self.test_app.get(self.url)
    self.assertEqual(200, response.status_int)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        queue_names='flake-detection-queue')
    self.assertEqual(2, len(tasks))
    self.assertTrue(mocked_is_request_from_appself.called)


class UpdateFlakeCountsTaskTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/flake/detection/task/update-flake-counts',
           update_flake_counts.UpdateFlakeCountsTask),
      ],
      debug=True)

  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  @mock.patch.object(update_flake_counts_service, 'UpdateFlakeCounts')
  def testUpdateFlakeCountsTask(self, mocked_service,
                                mocked_is_request_from_appself):
    response = self.test_app.get('/flake/detection/task/update-flake-counts')
    self.assertEqual(200, response.status_int)
    self.assertTrue(mocked_service.called)
    self.assertTrue(mocked_is_request_from_appself.called)
