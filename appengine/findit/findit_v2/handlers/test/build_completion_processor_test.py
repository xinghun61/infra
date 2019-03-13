# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

import webapp2

from testing_utils import testing

from findit_v2.handlers import build_completion_processor


class BuildCompletionProcessorTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/url', build_completion_processor.BuildCompletionProcessor),
  ],
                                       debug=True)

  @mock.patch('findit_v2.services.api.OnBuildCompletion')
  def testBucketNameShorten(self, mocked_func):
    data = {
        'project': 'chromium',
        'bucket': 'luci.chromium.ci',
        'builder_name': 'Linux Builder',
        'build_id': 123,
        'build_result': 'FAILURE',
    }
    headers = {'X-AppEngine-QueueName': 'task_queue'}
    response = self.test_app.post_json('/url', data, headers=headers)
    self.assertEquals(200, response.status_int)
    mocked_func.assert_called_once_with('chromium', 'ci', 'Linux Builder', 123,
                                        'FAILURE')
