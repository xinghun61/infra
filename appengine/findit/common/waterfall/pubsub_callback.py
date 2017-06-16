# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from gae_libs import token
from waterfall import waterfall_config


def GetVerificationToken(
    key_name, notification_id, action_id):
  return token.GenerateAuthToken(key_name, notification_id, action_id=action_id)


def GetTryJobTopic():
  return waterfall_config.GetTryJobSettings().get('pubsub_topic')


def GetSwarmingTopic():
  return waterfall_config.GetTryJobSettings().get('pubsub_swarming_topic')


def MakeTryJobPubsubCallback(notification_id):
  """Creates callback for buildbucket to notify us of status changes."""
  user_data = json.dumps({'Message-Type': 'BuildbucketStatusChange',
                          'Notification-Id': notification_id})
  return {'topic': GetTryJobTopic(),
          'auth_token': GetVerificationToken(
              'try_job_pubsub', 'try_job', notification_id),
          'user_data': user_data}


def MakeSwarmingPubsubCallback(notification_id):
  """Creates callback for swarming to notify us of status changes."""
  user_data = json.dumps({'Message-Type': 'SwarmingTaskStatusChange',
                          'Notification-Id': notification_id})
  return {'topic': GetSwarmingTopic(),
          'auth_token': GetVerificationToken(
              'swarming_pubsub', 'swarming', notification_id),
          'user_data': user_data}