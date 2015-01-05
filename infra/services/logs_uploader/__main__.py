#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Upload Buildbot logs to Google Cloud Storage.

This program avoids to load the Buildbot master by only querying it for
metadata (JSON interface). All log files are read directly from disk. Thus
it has to run on the master machine itself.

"""

import argparse
import logging
import os
import sys

from infra.libs import logs as infra_logs
from infra.services.logs_uploader import logs_uploader

LOGGER = logging.getLogger(__name__)


def parse_args(argv):
  parser = argparse.ArgumentParser(
    prog='python -m %s' % __package__,
    description='Upload logs to google storage.')
  parser.add_argument('--dry-run', action='store_true', default=False,
                      help='Do not write anything.')
  parser.add_argument('--waterfall-url',
                      help='waterfall main URL. Usually http://localhost:XXXX')
  parser.add_argument('--master-name', required=True,
                      help='name of the master to query. e.g. "chromium"')
  parser.add_argument('--builder-name',
                      help='name of the builder to query. e.g. "Linux".'
                           'Must be under specified master. If unspecified, '
                           'all builders are considered.')
  parser.add_argument('--bucket', default=None,
                      help='name of the bucket to use to upload logs, '
                           'optional.')
  parser.add_argument('--limit', default=10, type=int,
                      help='Maximum number of builds to upload in this run.')
  parser.add_argument('--nice', default=10, type=int,
                      help='Amount of niceness to add to this process and its'
                      'subprocesses')

  infra_logs.add_argparse_options(parser)

  args = parser.parse_args(argv)
  if args.master_name.startswith('master.'):
    args.master_name = args.master_name[7:]

  return args


def initial_setup(argv):
  """Actions before logging is set up."""
  options = parse_args(argv)

  logs_uploader.setup_logging(
    LOGGER,
    logs_uploader.get_master_directory(options.master_name),
    log_level=options.log_level)
  return options


def main(options):
  """Run the uploader.

  Logging is supposed to be set up prior to calling this function.
  """
  LOGGER.info('-- uploader starting --')
  try:
    os.nice(options.nice)
  except OSError:
    LOGGER.warn('Failed to set nice to %d', options.nice)

  return logs_uploader.main(options)


if __name__ == '__main__':
  # Error out by default, since no errors should go unnoticed.
  retcode = 1
  opts = initial_setup(sys.argv[1:])

  try:
    retcode = main(opts)
  except Exception:
    LOGGER.exception("Uncaught exception during execution")
    retcode = 1
  LOGGER.info('-- uploader shutting down with code %d --', retcode)
  sys.exit(retcode)
