# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import pickle

import webapp2

from testing_utils import testing

from common import constants
from handlers.process_flake_swarming_task_request import (
    ProcessFlakeSwarmingTaskRequest)
from waterfall.flake import trigger_flake_swarming_task_service_pipeline


class ProcessFlakeSwarmingTaskRequestTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/process-flake-swarming-task-request',
           ProcessFlakeSwarmingTaskRequest),
      ],
      debug=True)

  @mock.patch.object(trigger_flake_swarming_task_service_pipeline,
                     'ScheduleFlakeSwarmingTask')
  def testTaskQueueCanRequestAnalysis(self, mocked_func):
    response = self.test_app.post(
        '/process-flake-swarming-task-request',
        params=pickle.dumps(('m', 'b', 123, 's', 't', 100, 'email')),
        headers={'X-AppEngine-QueueName': 'task_queue'},
    )
    self.assertEquals(200, response.status_int)
    mocked_func.assert_called_once_with(
        'm', 'b', 123, 's', 't', 100, 'email',
        queue_name=constants.WATERFALL_FLAKE_SWARMING_TASK_REQUEST_QUEUE)
