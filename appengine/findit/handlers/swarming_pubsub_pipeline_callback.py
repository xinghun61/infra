# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This is the endpoint where we expect Swarming pubsub notifications."""

from gae_libs.handlers.pubsub_pipeline_callback import PubSubPipelineCallback
from waterfall import waterfall_config


class SwarmingPubSubPipelineCallback(PubSubPipelineCallback):
  auth_scope = 'pubsub'
  user_id = 'swarming'

  def GetValidHoursOfAuthToken(self):
    return waterfall_config.GetSwarmingSettings().get('task_timeout_hours', 24)
