# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import logging

from common import constants
from common import appengine_util
from common.base_handler import BaseHandler
from common.base_handler import Permission
from crash import crash_pipeline
from crash.crash_report import CrashReport
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.http.http_client_appengine import HttpClientAppengine
from model.crash.crash_config import CrashConfig


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
      ScheduleNewAnalysis(crash_data)

    except (KeyError, ValueError):  # pragma: no cover.
      # TODO: save exception in datastore and create a page to show them.
      logging.exception('Failed to process crash message')
      logging.info(self.request.body)


# TODO(http://crbug.com/659346): we don't cover anything after the
# call to _NeedsNewAnalysis.
def ScheduleNewAnalysis(crash_data):
  """Creates a pipeline object to perform the analysis, and start it.

  If we can detect that the analysis doesn't need to be performed
  (e.g., it was already performed, or the ``crash_data`` is empty so
  there's nothing we can do), then we will skip creating the pipeline
  at all.

  Args:
    crash_data (JSON): ??

  Returns:
    True if we started a new pipeline; False otherwise.
  """
  client_id = crash_data['client_id']
  # N.B., must call FinditForClientID indirectly, for mock testing.
  findit_client = crash_pipeline.FinditForClientID(
      client_id, CachedGitilesRepository.Factory(HttpClientAppengine()),
      CrashConfig.Get())

  # Check policy and modify the crash_data as needed.
  crash_data = findit_client.CheckPolicy(crash_data)
  if crash_data is None:
    return False

  # Detect the regression range, and decide if we actually need to
  # run a new anlaysis or not.
  if not findit_client._NeedsNewAnalysis(crash_data):
    return False

  crash_identifiers = crash_data['crash_identifiers']
  # N.B., we cannot pass ``self`` directly to the _pipeline_cls, because
  # it is not JSON-serializable (and there's no way to make it such,
  # since JSON-serializability is defined by JSON-encoders rather than
  # as methods on the objects being encoded).
  pipeline = crash_pipeline.CrashWrapperPipeline(client_id, crash_identifiers)
  # Attribute defined outside __init__ - pylint: disable=W0201
  pipeline.target = appengine_util.GetTargetNameForModule(
      constants.CRASH_BACKEND[client_id])
  queue_name = constants.CRASH_ANALYSIS_QUEUE[client_id]
  pipeline.start(queue_name=queue_name)
  logging.info('New %s analysis is scheduled for %s', client_id,
               repr(crash_identifiers))
  return True
