# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from infra.libs.event_mon.chrome_infra_log_pb2 import ChromeInfraEvent
from infra.libs.event_mon.chrome_infra_log_pb2 import ServiceEvent
from infra.libs.event_mon.log_request_lite_pb2 import LogRequestLite
from infra.libs.event_mon import config, router

EVENT_TYPES = ('START', 'STOP', 'UPDATE', 'CURRENT_VERSION')
TIMESTAMP_KINDS = (None, 'UNKNOWN', 'POINT', 'BEGIN', 'END')

def send_service_event(event_type,
                       timestamp_kind='POINT',
                       event_timestamp=None,
                     ):
  """Send service event.

  Returns:
    success (bool): False if some error happened.
  """

  if event_type not in EVENT_TYPES:
    logging.error('Invalid value for event_type: %s' % str(event_type))
    return False
  if timestamp_kind not in TIMESTAMP_KINDS:
    logging.error('Invalid value for timestamp_kind: %s' %
                 str(timestamp_kind))
    return False
  if not isinstance(event_timestamp, (int, float, None.__class__ )):
    logging.error('Invalid type for event_timestamp. Needs a number, got %s'
                  % str(type(event_timestamp)))
    return False

  event = ChromeInfraEvent()
  event.CopyFrom(config.cache['default_event'])
  event.service_event.type = getattr(ServiceEvent, event_type)

  if timestamp_kind:
    event.timestamp_kind = getattr(ChromeInfraEvent, timestamp_kind)

  log_event = LogRequestLite.LogEventLite()
  log_event.event_time_ms = event_timestamp or router.time_ms()
  log_event.source_extension = event.SerializeToString()
  return config._router.push_event(log_event)
