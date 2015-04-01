# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from infra.libs.event_mon.chrome_infra_log_pb2 import ChromeInfraEvent
from infra.libs.event_mon.chrome_infra_log_pb2 import ServiceEvent
from infra.libs.event_mon.log_request_lite_pb2 import LogRequestLite
from infra.libs.event_mon import config, router

EVENT_TYPES = ('START', 'STOP', 'UPDATE', 'CURRENT_VERSION', 'CRASH')
TIMESTAMP_KINDS = (None, 'UNKNOWN', 'POINT', 'BEGIN', 'END')

# Maximum size of stack trace sent in an event, in characters.
STACK_TRACE_MAX_SIZE = 1000


def _get_service_event(event_type,
                       timestamp_kind='POINT',
                       event_timestamp=None,
                       code_version=None,
                       stack_trace=None):
  """Compute a ChromeInfraEvent filled with a ServiceEvent.

  Args:
    event_type (string): any name of enum ServiceEvent.ServiceEventType.
      ('START', 'STOP', 'UPDATE', 'CURRENT_VERSION', 'CRASH')
    timestamp_kind (string): any of ('POINT', 'BEGIN', 'END').
    event_timestamp (int or float): timestamp of when the event happened
      as a number of milliseconds since the epoch. If not provided, the
      current time is used.
    code_version (list/tuple of dict or None): required keys are
        'source_url' -> full url to the repository
        'revision' -> (string) git sha1 or svn revision number.
      optional keys are
        'dirty' -> boolean. True if the local source tree has local
            modification.
        'version' -> manually-set version number (like 'v2.6.0')
    stack_trace (str): when event_type is 'CRASH', stack trace of the crash
      as a string. String is truncated to 1000 characters (the last ones
      are kept). Use traceback.format_exc() to get the stack trace from an
      exception handler.

  Returns:
    event (log_request_lite_pb2.LogRequestLite.LogEventLite):
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

  if code_version is None:
    code_version = ()
  if not isinstance(code_version, (tuple, list)):
    logging.error('Invalid type provided to code_version argument in '
                  '_get_service_event. Please fix the calling code. '
                  'Type provided: %s, expected list, tuple or None.'
                  % str(type(code_version)))
    code_version = ()

  for version_d in code_version:
    try:
      if 'source_url' not in version_d:
        logging.error('source_url missing in %s', version_d)
        continue

      version = event.service_event.code_version.add()
      version.source_url = version_d['source_url']
      if 'revision' in version_d:
        # Rely on the url to switch between svn and git because an
        # abbreviated sha1 can sometime be confused with an int.
        if version.source_url.startswith('svn://'):
          version.svn_revision = int(version_d['revision'])
        else:
          version.git_hash = version_d['revision']

      if 'version' in version_d:
        version.version = version_d['version']
      if 'dirty' in version_d:
        version.dirty = version_d['dirty']

    except TypeError:
      logging.exception('Invalid type provided to code_version argument in '
                        '_get_service_event. Please fix the calling code.')
      continue

  if isinstance(stack_trace, basestring):
    if event_type != 'CRASH':
      logging.error('stack_trace provide for an event different from CRASH.'
                    ' Got: %s', event_type)
    event.service_event.stack_trace = stack_trace[-STACK_TRACE_MAX_SIZE:]
  else:
    if stack_trace is not None:
      logging.error('stack_trace should be a string, got %s',
                    stack_trace.__class__.__name__)
  if timestamp_kind:
    event.timestamp_kind = getattr(ChromeInfraEvent, timestamp_kind)

  log_event = LogRequestLite.LogEventLite()
  log_event.event_time_ms = event_timestamp or router.time_ms()
  log_event.source_extension = event.SerializeToString()
  return log_event


def send_service_event(event_type,
                       timestamp_kind='POINT',
                       event_timestamp=None,
                       code_version=(),
                       stack_trace=None):
  """Send service event.

  Args:
    event_type (string): any name of enum ServiceEvent.ServiceEventType.
      ('START', 'STOP', 'UPDATE', 'CURRENT_VERSION', 'CRASH')
    timestamp_kind (string): any of ('POINT', 'BEGIN', 'END').
    event_timestamp (int or float): timestamp of when the event happened
      as a number of milliseconds since the epoch. If not provided, the
      current time is used.
    stack_trace (str): when event_type is 'CRASH', stack trace of the crash
      as a string. String is truncated to 1000 characters (the last ones
      are kept). Use traceback.format_exc() to get the stack trace from an
      exception handler.

  Returns:
    success (bool): False if some error happened.
  """
  log_event = _get_service_event(event_type,
                                 timestamp_kind=timestamp_kind,
                                 event_timestamp=event_timestamp,
                                 code_version=code_version,
                                 stack_trace=stack_trace)

  return config._router.push_event(log_event)
