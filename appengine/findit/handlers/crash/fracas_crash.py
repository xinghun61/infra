# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import logging

from common import constants
from common.base_handler import BaseHandler
from common.base_handler import Permission
from crash import fracas_crash_pipeline
from model.crash.crash_config import CrashConfig


FRACAS_ANALYSIS_QUEUE = 'fracas-crash-queue'


class FracasCrash(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandlePost(self):
    """Handles push delivery from Pub/Sub for crash data.

    The crash data should be in the following json format:
    {
      'channel': 'canary',
      'platform': 'win',
      'signature': 'namesapce1:namespace2:class_name:func_name',
      'stack_trace': 'frame1\nframe2\nframe3',
      'chrome_version': '50.0.2500.0',
      'versions_to_cpm': {
        '50.0.2500.0': 1.2,
        '50.0.2499.0': 1.0,
      },
    }
    """
    token = self.request.get('token', '').strip()
    crash_config = CrashConfig.Get()
    if token != crash_config.fracas.get('crash_data_push_token'):
      logging.warning('Unauthorized access.')
      return self.CreateError(
          'Unauthorized access: invalid token "%s"' % token, 403)

    received_message = json.loads(self.request.body)
    pubsub_message = received_message['message']
    crash_data = json.loads(base64.b64decode(pubsub_message['data']))

    logging.info('Processing message %s from subscription %s.',
                 pubsub_message['message_id'], received_message['subscription'])

    fracas_crash_pipeline.ScheduleNewAnalysisForCrash(
        crash_data['channel'], crash_data['platform'], crash_data['signature'],
        crash_data['stack_trace'], crash_data['chrome_version'],
        crash_data['versions_to_cpm'],
        queue_name=constants.CRASH_ANALYSIS_FRACAS_QUEUE)
