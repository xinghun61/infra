# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This is the endpoint where we expect Buildbucket pubsub notifications."""

import json

from gae_libs.handlers.pubsub_pipeline_callback import PubSubPipelineCallback
from waterfall import waterfall_config


class TryJobPubSubPipelineCallback(PubSubPipelineCallback):
  auth_scope = 'pubsub'
  user_id = 'buildbucket'

  def GetValidHoursOfAuthToken(self):
    return waterfall_config.GetTryJobSettings().get('job_timeout_hours', 10)

  def GetAdditionalParameters(self, _message, message_data):
    return {'build_json': json.dumps(message_data['build'])}
