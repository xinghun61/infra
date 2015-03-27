# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for logging.

Example usage:

.. code-block:: python

    import logging
    from infra.libs import logs
    logger = logging.getLogger('foo')
    logs.add_handler(logger, timezone='US/Pacific')
    logger.info('test message')

The last line should print something like::

  [I2014-06-27T11:42:32.418716-07:00 7082 logs:71] test message

"""

import datetime
import logging

import pytz


class InfraFilter(logging.Filter):  # pragma: no cover
  """Adds fields used by the infra-specific formatter.

  Fields added:

  - 'iso8601': timestamp
  - 'severity': one-letter indicator of log level (first letter of levelname).

  Args:
    timezone (str): timezone in which timestamps should be printed.
  """
  def __init__(self, timezone):
    super(InfraFilter, self).__init__()
    self.tz = pytz.timezone(timezone)

  def filter(self, record):
    dt = datetime.datetime.fromtimestamp(record.created, tz=pytz.utc)
    record.iso8601 = self.tz.normalize(dt).isoformat()
    record.severity = record.levelname[0]
    return True


class InfraFormatter(logging.Formatter):  # pragma: no cover
  """Formats log messages in a standard way.

  This object processes fields added by :class:`InfraFilter`.
  """
  def __init__(self):
    super(InfraFormatter, self).__init__('[%(severity)s%(iso8601)s %(process)d '
                                         '%(thread)d '
                                         '%(module)s:%(lineno)s] %(message)s')


def add_handler(logger, handler=None, timezone='UTC',
                level=logging.WARN):  # pragma: no cover
  """Configures and adds a handler to a logger the standard way for infra.

  Args:
    logger (logging.Logger): logger object obtained from `logging.getLogger`.
    handler (logging.Handler): handler to add to the logger. defaults to
       logging.StreamHandler.
    timezone (str): timezone to use for timestamps.

    level (int): logging level. Could be one of DEBUG, INFO, WARN, CRITICAL

  Example usage::

    import logging
    from infra.libs import logs
    logger = logging.getLogger('foo')
    logs.add_handler(logger, timezone='US/Pacific')
    logger.info('test message')

  The last line should print something like::

    [I2014-06-27T11:42:32.418716-07:00 7082 logs:71] test message

  """
  handler = handler or logging.StreamHandler()
  handler.addFilter(InfraFilter(timezone))
  handler.setFormatter(InfraFormatter())
  handler.setLevel(level=level)
  logger.addHandler(handler)

  # Formatters only get messages that pass this filter: let everything through.
  logger.setLevel(level=logging.DEBUG)


def add_argparse_options(parser,
                         default_level=logging.WARN):  # pragma: no cover
  """Adds logging related options to an argparse.ArgumentParser.

  See also: :func:`process_argparse_options`
  """
  parser = parser.add_argument_group('Logging Options')
  g = parser.add_mutually_exclusive_group()
  g.set_defaults(log_level=default_level)
  g.add_argument('--quiet', action='store_const', const=logging.ERROR,
                 dest='log_level', help='Make the output quieter.')
  g.add_argument('--warning', action='store_const', const=logging.WARN,
                 dest='log_level',
                 help='Set the output to an average verbosity.')
  g.add_argument('--verbose', action='store_const', const=logging.INFO,
                 dest='log_level', help='Make the output louder.')
  g.add_argument('--debug', action='store_const', const=logging.DEBUG,
                 dest='log_level', help='Make the output really loud.')


def process_argparse_options(options, logger=None):  # pragma: no cover
  """Handles logging argparse options added in 'add_argparse_options'.

  Configures 'logging' module.

  Args:
    options: return value of argparse.ArgumentParser.parse_args.
    logger (logging.Logger): logger to apply the configuration to.

  Example usage::

    import argparse
    import sys
    import infra.libs.logs

    parser = argparse.ArgumentParser()
    infra.libs.logs.add_argparse_options(parser)

    options = parser.parse_args(sys.path[1:])
    infra.libs.logs.process_argparse_options(options)
  """
  if logger is None:
    logger = logging.root
  add_handler(logger, level=options.log_level)
