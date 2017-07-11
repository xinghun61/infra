# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import pickle

import webapp2

from testing_utils import testing

from handlers.process_flake_swarming_task_request import (
    ProcessFlakeSwarmingTaskRequest)


class ProcessFlakeSwarmingTaskRequestTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/process-flake-swarming-task-request',
           ProcessFlakeSwarmingTaskRequest),
      ],
      debug=True)

  def testNonAdminCannotSendRequest(self):
    self.test_app.post(
        '/process-flake-swarming-task-request?format=json',
        params='',
        status=401)

  def testCorpUserCanRequestFlakeSwarmingTask(self):
    self.mock_current_user(user_email='test@google.com')

    response = self.test_app.post(
        '/process-flake-swarming-task-request',
        params=pickle.dumps(('m', 'b', 123, 's', 't', 100, 'email')))
    self.assertEquals(200, response.status_int)
