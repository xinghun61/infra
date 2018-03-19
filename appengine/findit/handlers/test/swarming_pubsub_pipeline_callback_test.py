# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from testing_utils import testing

from waterfall import waterfall_config

from handlers.swarming_pubsub_pipeline_callback import (
    SwarmingPubSubPipelineCallback)


class SwarmingPubSubPipelineCallbackTest(testing.AppengineTestCase):

  @mock.patch.object(
      waterfall_config,
      'GetSwarmingSettings',
      return_value={
          'task_timeout_hours': 2
      })
  def testGetValidHoursOfAuthToken(self, _):
    self.assertEqual(
        2,
        SwarmingPubSubPipelineCallback().GetValidHoursOfAuthToken())
