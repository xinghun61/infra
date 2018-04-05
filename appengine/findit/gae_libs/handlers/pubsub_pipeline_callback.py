# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This serves as a generic handler for PubSub callback for async pipelines."""

import base64
import json
import logging

from gae_libs import token
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from gae_libs.pipelines import AsynchronousPipeline


class PubSubPipelineCallback(BaseHandler):
  """Runs pipeline callback upon Buildbucket/Swarming PubSub notification.

  Subclass must specify the auth_scope & user_id in parity to the
  corresponding pipeline, and also implement the function
  `GetValidHoursOfAuthToken`. Optionally, subclass could implement the function
  `GetAdditionalParameters` to pass additional parameters to pipeline
  callback.
  """

  PERMISSION_LEVEL = Permission.ANYONE  # Proected with login:admin.
  auth_scope = None  # The auth token scope for the PubSub message.
  user_id = None  # The user who pushed the PubSub message.

  def GetValidHoursOfAuthToken(self):
    """Returns the hours for the auth token to expire."""
    raise NotImplementedError()

  def GetAdditionalParameters(self, message, message_data):  # pylint: disable=unused-argument
    """Returns additional parameters to pass over to the pipeline callback.

    Args:
      message (dict): A dict representing the whole PubSub message.
      message_data (dict): A dict representing the message data only.

    Returns:
      A dict mapping from parameter name to string value.
    """
    return {}

  def HandlePost(self):
    assert self.auth_scope, 'Auth scope must be provided.'
    assert self.user_id, 'User id must be provided.'

    logging.debug('Post body: %s', self.request.body)

    try:
      envelope = json.loads(self.request.body)
      auth_token = envelope['message']['attributes']['auth_token']
      message_data = json.loads(base64.b64decode(envelope['message']['data']))
      user_data = json.loads(
          message_data.get('user_data') or message_data.get('userdata'))
      pipeline_id = user_data['runner_id']

      valid, expired = token.ValidateAuthToken(
          self.auth_scope,
          auth_token,
          self.user_id,
          action_id=pipeline_id,
          valid_hours=self.GetValidHoursOfAuthToken())
      if not valid or expired:
        # Ignore requests with invalid or expired auth token.
        logging.warning('Auth token: valid=%s, expired=%s', valid, expired)
        return

      pipeline = AsynchronousPipeline.from_id(pipeline_id)
      if not pipeline or not isinstance(pipeline, AsynchronousPipeline):
        # Ignore requests targeted at invalid pipelines.
        logging.warning('Pipeline not found or not async: %s', pipeline_id)
        return

      message_id = envelope['message']['message_id']
      parameters = self.GetAdditionalParameters(envelope['message'],
                                                message_data)
      # The pipeline will schedule the callback task to be run in the same
      # target version and task queue as itself.
      # Use the message id from PubSub as task name to avoid duplicate callback
      # tasks because PubSub could push the same message multiple times.
      pipeline.ScheduleCallbackTask(name=message_id, parameters=parameters)
    except (ValueError, KeyError) as e:
      # Ignore requests with invalid message.
      logging.warning('Unexpected PubSub message format: %s', e.message)
