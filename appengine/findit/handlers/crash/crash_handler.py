# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import logging

from common import constants
from common.base_handler import BaseHandler
from common.base_handler import Permission
from crash import crash_pipeline


class CrashHandler(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandlePost(self):
    """Handles push delivery from Pub/Sub for crash data.

    The crash data should be in the following json format:
    {
        'customized_data': {...},
        'chrome_version': '51.0.2704.28',
        'signature': 'blink::FramePainter::paintContents',
        'client_id': 'fracas|cracas|clusterfuzz',
        'platform': 'android',
        'crash_identifiers': {...},
        'stack_trace': 'CRASHED [SIGILL @ 0x5320e570]\\n#0 0x5320e570...'
    }

    customized_data, client_id and crash_identifiers vary from client to client.
    For example, for fracas,

    customized_data: {
        'trend_type': 'd',  # *see supported types below
        'channel': 'beta',
        'historical_metadata': [
          {
              'report_number': 0,
              'cpm': 0.0,
              'client_number': 0,
              'chrome_version': '51.0.2704.103'
          },
          ...
          {
              'report_number': 10,
              'cpm': 2.1,
              'client_number': 8,
              'chrome_version': '53.0.2768.0'
          },
        ]
    }

    crash_identifiers: {
        'platform': 'mac',
        'version': '52.0.2743.41',
        'process_type': 'browser',
        'channel': 'beta',
        'signature': '[ThreadWatcher UI hang] base::MessagePumpBase::Run'
    }

    customized_data, client_id and crash_identifiers vary from client to client.
    For example, for fracas,

    customized_data: {
      "trend_type": "d",  # *see supported types below
      "channel": "beta",
      "historical_metadata": [
        {
          "report_number": 0,
          "cpm": 0.0,
          "client_number": 0,
          "chrome_version": "51.0.2704.103"
        },
        ...
        {
          "report_number": 10,
          "cpm": 2.1,
          "client_number": 8,
          "chrome_version": "53.0.2768.0"
        },
      ]
    }

    crash_identifiers: {
      "platform": "mac",
      "version": "52.0.2743.41",
      "process_type": "browser",
      "channel": "beta",
      "signature": "[ThreadWatcher UI hang] base::MessagePumpCFRunLoopBase::Run"
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

      crash_pipeline.ScheduleNewAnalysisForCrash(
          crash_data['crash_identifiers'],
          crash_data['chrome_version'],
          crash_data['signature'],
          crash_data['client_id'],
          crash_data['platform'],
          crash_data['stack_trace'],
          crash_data['customized_data'],
          queue_name=constants.CRASH_ANALYSIS_QUEUE[crash_data['client_id']])
    except (KeyError, ValueError):  # pragma: no cover.
      # TODO: save exception in datastore and create a page to show them.
      logging.exception('Failed to process crash message')
      logging.info(self.request.body)
