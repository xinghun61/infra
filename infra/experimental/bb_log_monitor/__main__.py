#!/usr/bin/env python --
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import logging
import os
import re
import sys

from infra.libs import ts_mon, logs

# Regex to identify build logs. e.g., "24-log-shell-stdio". Note that several
# build logs may be compressed (extension); we'll probably want to skip these.
BUILDLOG_RE = re.compile(r'(?P<buildnum>\d+)-log-(?P<step>.+)')


def get_builder_state(metric, builder_name, builder_path):
  # List every file in this directory. Log files that are monitored as the
  # unzipped output files, which mean they don't have an extension.
  for n in os.listdir(builder_path):
    path = os.path.join(builder_path, n)

    # Skip files with an extension.
    _, ext = os.path.splitext(n)
    if ext:
      logging.debug("Skipping file with extension: %s", path)
      continue

    # Skip files that aren't log files.
    match = BUILDLOG_RE.match(n)
    if not match:
      logging.debug("Skipping unmatching path: %s", path)
      continue
    buildnum, step = match.group('buildnum'), match.group('step')
    logging.debug("Processing log file '%s :: %s' for %s at: %s",
                  buildnum, step, builder_name, path)

    try:
      path_stat = os.stat(path)
    except OSError as e:
      logging.error("Error while statting %s: %s", path, e)
      continue

    metric.set(path_stat.st_size, fields={
      'builder': builder_name,
      'build_number': int(buildnum),
      'step': step,
    })


def get_master_state(master_path, master_target):
  if not os.path.isdir(master_path):
    logging.error("Master path is not a directory: %s", master_path)
    return None

  active_log_size = ts_mon.GaugeMetric('master/active_log_size',
                                       target=master_target)
  for d in os.listdir(master_path):
    path = os.path.join(master_path, d)
    if not os.path.isdir(path):
      continue
    get_builder_state(active_log_size, d, path)


def master_path_to_name(path):
  result = os.path.split(path.rstrip(os.sep))[1]
  if result.startswith('master.'):
    result = result[7:]
  return result


def main(args):
  parser = argparse.ArgumentParser()
  parser.add_argument('-n', '--nice', type=int, metavar='VALUE',
      help='Set the nice level of the process to VALUE prior to execution.')
  parser.add_argument('statefile',
      help='The path of the state file. If non-existent, one will be created; '
           'otherwise, the existing one will be updated.')
  parser.add_argument('master_paths', nargs='+',
      help='The paths to the master base directories to monitor. Consider '
           'the /path/to/build/masters/master.* wildcard to specify all of '
           'them.')

  logs.add_argparse_options(parser)
  ts_mon.add_argparse_options(parser)

  # Parse arguments.
  args = parser.parse_args(args)
  logs.process_argparse_options(args)
  ts_mon.process_argparse_options(args)

  # Try setting the nice value; if it fails, eat the error and continue.
  if args.nice:
    logging.debug("Setting process 'nice' to: %d", args.nice)
    try:
      os.nice(args.nice)
    except OSError as e:
      logging.error("Failed to update 'nice' to %d: %s", args.nice, e)

  # Update global state calculations.
  logging.info("Pulling master state from: %s", args.master_paths)
  for master_path in args.master_paths:
    master_name = master_path_to_name(master_path)

    # Log to the target: buildbot/master/<master_name>
    target = ts_mon.TaskTarget(
        'buildbot/master',
        master_name,
        args.ts_mon_task_region,
        args.ts_mon_task_hostname,
        args.ts_mon_task_number)
    logging.info("Collecting log state for master '%s' at: %s",
                 master_name, master_path)
    get_master_state(master_path, target)

  logging.info("Flushing collected information.")
  ts_mon.flush()
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
