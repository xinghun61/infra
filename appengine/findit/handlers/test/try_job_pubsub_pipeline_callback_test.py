# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from testing_utils import testing

from waterfall import waterfall_config

from handlers.try_job_pubsub_pipeline_callback import (
    TryJobPubSubPipelineCallback)


class TryJobPubSubPipelineCallbackTest(testing.AppengineTestCase):

  @mock.patch.object(
      waterfall_config,
      'GetTryJobSettings',
      return_value={
          'job_timeout_hours': 2
      })
  def testGetValidHoursOfAuthToken(self, _):
    self.assertEqual(2,
                     TryJobPubSubPipelineCallback().GetValidHoursOfAuthToken())

  def testGetAdditionalParameters(self):
    message = {
        'attributes': {
            'a': 1
        },
        'data': 'encoded-data',
    }
    message_data = {
        'user_data': {
            'runner_id': 'id',
        },
        'build': {
            'k': 'v',
        },
    }
    result = TryJobPubSubPipelineCallback().GetAdditionalParameters(
        message, message_data)
    self.assertDictEqual({'build_json': '{"k": "v"}'}, result)
