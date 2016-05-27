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


class FracasCrash(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandlePost(self):
    """Handles push delivery from Pub/Sub for crash data.

    The crash data should be in the following json format:
    {
      "customized_data": {
        "channel": "beta",
        "historic_metadata": [
          {
            "chrome_version": "51.0.2693.2",
            "cpm": 0.0610491148
          },
          {
            "chrome_version": "51.0.2704.10",
            "cpm": 0.0490386976
          },
          {
            "chrome_version": "52.0.2718.2",
            "cpm": 0.0040353297
          }
        ]
      },
      "chrome_version": "51.0.2704.28",
      "signature": "blink::FramePainter::paintContents",
      "client_id": "fracas",
      "platform": "android",
      "crash_identifiers": {
        "chrome_version": "51.0.2704.28",
        "signature": "blink::FramePainter::paintContents",
        "channel": "beta",
        "platform": "android",
        "process_type": null
      },
      "stack_trace": "CRASHED [SIGILL @ 0x5320e570]\\n#0 0x5320e570..."
    }
    """
    try:
      received_message = json.loads(self.request.body)
      pubsub_message = received_message['message']
      crash_data = json.loads(base64.b64decode(pubsub_message['data']))

      logging.info('Processing message %s from subscription %s.',
                   pubsub_message['message_id'],
                   received_message['subscription'])

      logging.info('Crash data is %s', json.dumps(crash_data))

      fracas_crash_pipeline.ScheduleNewAnalysisForCrash(
          crash_data['crash_identifiers'],
          crash_data['chrome_version'],
          crash_data['signature'],
          crash_data['client_id'],
          crash_data['platform'],
          crash_data['stack_trace'],
          crash_data['customized_data']['channel'],
          crash_data['customized_data']['historical_metadata'],
          queue_name=constants.CRASH_ANALYSIS_FRACAS_QUEUE)
    except (KeyError, ValueError):  # pragma: no cover.
      # TODO: save exception in datastore and create a page to show them.
      logging.exception('Failed to process fracas message')
      logging.info(self.request.body)
