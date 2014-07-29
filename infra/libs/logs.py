# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for logging."""

import datetime
import logging

import pytz


class InfraFilter(logging.Filter):
  """Adds fields used by the infra-specific formatter.

  Fields added:
  - 'iso8601': timestamp
  - 'severity': one-letter indicator of log level (first letter of levelname).
  """
  def __init__(self, timezone):
    super(InfraFilter, self).__init__()
    self.tz = pytz.timezone(timezone)

  def filter(self, record):
    dt = datetime.datetime.fromtimestamp(record.created, tz=pytz.utc)
    record.iso8601 = self.tz.normalize(dt).isoformat()
    record.severity = record.levelname[0]
    return True


class InfraFormatter(logging.Formatter):
  """Formats log messages in a standard way.

  Works together with InfraFilter.
  """
  def __init__(self):
    super(InfraFormatter, self).__init__('[%(severity)s%(iso8601)s %(process)d '
                                         '%(module)s:%(lineno)s] %(message)s')


def add_handler(logger, handler=None, timezone='UTC', level=logging.INFO):
  """Configures and adds a handler to a logger, the standard way for infra.

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
    import infra.libs import logs
    logger = logging.getLogger('foo')
    logs.add_handler(logger, timezone='US/Pacific')
    logger.info('test message')

  The last line should print something like
  [I2014-06-27T11:42:32.418716-07:00 7082 logs:71] test message

  """
  handler = handler or logging.StreamHandler()
  handler.addFilter(InfraFilter(timezone))
  handler.setFormatter(InfraFormatter())
  handler.setLevel(level=level)
  logger.addHandler(handler)

  # Formatters only get messages that pass this filter: let everything through.
  logger.setLevel(level=logging.DEBUG)


def add_argparse_options(parser, default_level=logging.WARN):
  """Adds logging related options to an argparse.ArgumentParser."""
  g = parser.add_mutually_exclusive_group()
  g.set_defaults(log_level=default_level)
  g.add_argument('--quiet', action='store_const', const=logging.ERROR,
                 dest='log_level', help='Make the output quieter.')
  g.add_argument('--verbose', action='store_const', const=logging.INFO,
                 dest='log_level', help='Make the output louder.')
  g.add_argument('--debug', action='store_const', const=logging.DEBUG,
                 dest='log_level', help='Make the output really loud.')


def process_argparse_options(opts):
  """Handles logging argparse options added in 'add_argparse_options'.

  Configures 'logging' module.
  """
  add_handler(logging.root, level=opts.log_level)
