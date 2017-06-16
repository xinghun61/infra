# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
from testing_utils import testing

from common.waterfall import pubsub_callback


_DUMMY_CONFIG = {
    'pubsub_topic': 'projects/findit-for-me/topics/jobs',
    'pubsub_swarming_topic': 'projects/findit-for-me/topics/swarm'
}


class PubsubCallbackTest(testing.AppengineTestCase):

  @mock.patch.object(pubsub_callback.token, 'GenerateAuthToken',
                     return_value='token')
  def testGetVerificationToken(self, _):
    self.assertEqual('token', pubsub_callback.GetVerificationToken(
        'key', 'user', 'action'))

  @mock.patch.object(pubsub_callback.waterfall_config, 'GetTryJobSettings',
                     return_value=_DUMMY_CONFIG)
  def testGetTryJobTopic(self, _):
    self.assertEqual(_DUMMY_CONFIG['pubsub_topic'],
                     pubsub_callback.GetTryJobTopic())

  @mock.patch.object(pubsub_callback.waterfall_config, 'GetTryJobSettings',
                     return_value=_DUMMY_CONFIG)
  def testGetSwarmingTopic(self, _):
    self.assertEqual(_DUMMY_CONFIG['pubsub_swarming_topic'],
                     pubsub_callback.GetSwarmingTopic())

  @mock.patch.object(pubsub_callback.token, 'GenerateAuthToken',
                     return_value='token')
  @mock.patch.object(pubsub_callback.waterfall_config, 'GetTryJobSettings',
                     return_value=_DUMMY_CONFIG)
  def testMakeTryJobPubsubCallback(self, *_):
    notification_id = 'pipeline_id'
    expected_value = {
        'topic': _DUMMY_CONFIG['pubsub_topic'],
        'auth_token': 'token',
        'user_data': json.dumps({
            'Message-Type': 'BuildbucketStatusChange',
            'Notification-Id': notification_id
        })
    }
    self.assertEqual(expected_value,
                     pubsub_callback.MakeTryJobPubsubCallback(notification_id))

  @mock.patch.object(pubsub_callback.token, 'GenerateAuthToken',
                     return_value='token')
  @mock.patch.object(pubsub_callback.waterfall_config, 'GetTryJobSettings',
                     return_value=_DUMMY_CONFIG)
  def testMakeSwarmingPubsubCallback(self, *_):
    notification_id = 'pipeline_id'
    expected_value = {
        'topic': _DUMMY_CONFIG['pubsub_swarming_topic'],
        'auth_token': 'token',
        'user_data': json.dumps({
            'Message-Type': 'SwarmingTaskStatusChange',
            'Notification-Id': notification_id
        })
    }
    self.assertEqual(
        expected_value,
        pubsub_callback.MakeSwarmingPubsubCallback(notification_id))