# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for logging."""

import datetime
import logging
from infra.ext import pytz


class InfraFilter(logging.Filter):
  """Add fields used by the infra-specific formatter.

  Fields added:
  - 'iso8601': timestamp
  - 'severity': one-letter indicator of log level (first letter of levelname).
  """
  def __init__(self, timezone):
    logging.Filter.__init__(self)
    self.tz = pytz.timezone(timezone)

  def filter(self, record):
    dt = datetime.datetime.fromtimestamp(record.created, tz=pytz.utc)
    record.iso8601 = self.tz.normalize(dt).isoformat()
    record.severity = record.levelname[0]
    return True


def add_handler(logger, handler=None,
                timezone='UTC', level=logging.INFO):
  """Add a handler to a logger, the standard way for infra.

  Arguments:
  logger: a Logger object obtained from logging.getLogger().
  handler: a handler object from the logging module
     (defaults to logging.StreamHandler) to add to the logger.
  timezone: timezone from pytz to use for timestamps.
  level: logging level.

  Returns:
  None

  Example usage:
    import logging
    import infra.libs.logs
    logger = logging.getLogger('foo')
    infra.libs.logs.add_handler(logger, timezone='US/Pacific')
    logger.info('test message')

  The last line should print something like
  [I2014-06-27T11:42:32.418716-07:00 7082 logs:71] test message

  """
  logger.addFilter(InfraFilter(timezone))
  infra_formatter = logging.Formatter('[%(severity)s%(iso8601)s %(process)d '
                                      '%(module)s:%(lineno)s] %(message)s')

  if not handler:
    handler = logging.StreamHandler()
  handler.setFormatter(infra_formatter)
  handler.setLevel(level=level)
  logger.addHandler(handler)

  # formatters only get messages that pass this filter: let
  # everything through.
  logger.setLevel(level=logging.DEBUG)

