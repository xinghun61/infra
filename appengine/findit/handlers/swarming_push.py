# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This is the endpoint where we expect swarming pubsub notifications."""

import base64
import json
import logging

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from common import constants
from common.base_handler import BaseHandler
from common.base_handler import Permission
from common.waterfall.pubsub_callback import GetVerificationToken
from gae_libs import appengine_util
from model.wf_swarming_task import WfSwarmingTask
from model.flake.flake_swarming_task import FlakeSwarmingTask


class SwarmingPush(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandlePost(self):
    # TODO(robertocn): Find out why one of these works for local testing, and
    # the other one for deploy-test-prod
    try:
      envelope = json.loads(self.request.body)
    except ValueError:
      envelope = json.loads(self.request.params.get('data'))
    try:
      token = envelope['message']['attributes']['auth_token']
      if token != GetVerificationToken():
        return {'return_code': 400}
      payload = base64.b64decode(envelope['message']['data'])
      # Expected payload format:
      # json.dumps({
      #   'task_id': '123412342130498',  #Swarming task id
      #   'userdata': json.dumps({
      #       'Message-Type': 'SwarmingTaskStatusChange'}),
      #       # Plus any data from MakePubsubCallback
      #   })
      message = json.loads(payload)
      user_data = json.loads(message['userdata'])
      task_id = message['task_id']

      if user_data['Message-Type'] == 'SwarmingTaskStatusChange':
        for kind in [WfSwarmingTask, FlakeSwarmingTask]:
          swarming_task = kind.query(kind.task_id == task_id).get()
          if not swarming_task:
            continue
          if swarming_task.callback_url:
            url = swarming_task.callback_url
            # TODO(robertocn): After a transitional period, all swarming_task
            # entities should have a targed defined. Remove the or clause.
            target = swarming_task.callback_target or (
                appengine_util.GetTargetNameForModule(
                    constants.WATERFALL_BACKEND))
            taskqueue.add(method='GET', url=url, target=target,
                          queue_name=constants.WATERFALL_ANALYSIS_QUEUE)
            return {}
          else:
            logging.warning('The swarming task referenced by pubsub does not '
                            'have an associated pipeline callback url.')
            # We return 200 because we don't want pubsub to retry the push.
            return {}
        logging.warning('The task is not known by findit.')
        # We return 200 because we don't want pubsub to retry the push.
        return {}
      else:
        # We raise an exception instead of accepting the push because we might
        # be an older version (than the one that sent the new message type)
        raise Exception('Unsupported message type %s' % message['Message-Type'])
    except KeyError:
      raise Exception('The message was not in the expected format: \n'
                      '{"message": {\n'
                      '  "attributes": {\n'
                      '    "auth_token": <valid_token>,\n'
                      '  }\n'
                      '  "data": <serialization of {\n'
                      '    "task_id": <Swarming task id>,\n'
                      '    "userdata": <serialization of {\n'
                      '      "Message-Type": "SwarmingTaskStatusChange"\n'
                      '    }>\n'
                      '  }>\n'
                      '}}\n')
