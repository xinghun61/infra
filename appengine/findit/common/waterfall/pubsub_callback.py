# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from waterfall import waterfall_config


# TODO(robertocn): Remove these dummy values once the change is deployed and the
# config is saved to the data store.
_DUMMY_VERIFICATION_TOKEN = 'https://goo.gl/yYhr29'
_DUMMY_TRY_JOB_TOPIC = 'projects/findit-for-me/topics/jobs'
_DUMMY_SWARMING_TOPIC = 'projects/findit-for-me/topics/swarm'


def GetVerificationToken():  # pragma: no cover
  return waterfall_config.GetTryJobSettings().get(
      'pubsub_token', _DUMMY_VERIFICATION_TOKEN)


def GetTryJobTopic():  # pragma: no cover
  return waterfall_config.GetTryJobSettings().get(
      'pubsub_topic', _DUMMY_TRY_JOB_TOPIC)


def GetSwarmingTopic():  # pragma: no cover
  return waterfall_config.GetTryJobSettings().get(
      'pubsub_swarming_topic', _DUMMY_SWARMING_TOPIC)


def MakeTryJobPubsubCallback():  # pragma: no cover
  """Creates callback for buildbucket to notify us of status changes."""
  user_data = json.dumps({'Message-Type': 'BuildbucketStatusChange'})
  return {'topic': GetTryJobTopic(),
          'auth_token': GetVerificationToken(),
          'user_data': user_data}


def MakeSwarmingPubsubCallback():  # pragma: no cover
  """Creates callback for swarming to notify us of status changes."""
  user_data = json.dumps({'Message-Type': 'SwarmingTaskStatusChange'})
  return {'topic': GetSwarmingTopic(),
          'auth_token': GetVerificationToken(),
          'user_data': user_data}
