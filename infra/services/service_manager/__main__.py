#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import logging
import signal
import socket
import sys
import time

from infra.services.service_manager import config_watcher
from infra_libs import logs
from infra_libs import ts_mon


def parse_args(argv):
  p = argparse.ArgumentParser(
      description='Starts and stops machine-wide infra services with arguments '
                  'from config files')

  p.add_argument(
      '--state-directory',
      default='/var/run/infra-services',
      help='directory to store PID files (default %(default)s)')
  p.add_argument(
      '--config-directory',
      default='/etc/infra-services',
      help='directory to read JSON config files (default %(default)s)')
  p.add_argument(
      '--root-directory',
      default='/opt/infra-python',
      help='directory where the service_manager package is deployed. If this '
           'package is updated the process will exit')

  p.add_argument(
      '--config-poll-interval',
      default=10,
      help='how frequently (in seconds) to poll the config directory')
  p.add_argument(
      '--service-poll-interval',
      default=10,
      help='how frequently (in seconds) to restart failed services')

  logs.add_argparse_options(p)
  ts_mon.add_argparse_options(p)

  p.set_defaults(
      ts_mon_target_type='task',
      ts_mon_task_service_name='service_manager',
      ts_mon_task_job_name=socket.getfqdn(),
  )

  opts = p.parse_args(argv)

  logs.process_argparse_options(opts)
  ts_mon.process_argparse_options(opts)

  return opts


def main(argv):
  opts = parse_args(argv)

  watcher = config_watcher.ConfigWatcher(
      opts.config_directory,
      opts.config_poll_interval,
      opts.service_poll_interval,
      opts.state_directory,
      opts.root_directory)

  def sigint_handler(_signal, _frame):
    watcher.stop()

  try:
    previous_sigint_handler = signal.signal(signal.SIGINT, sigint_handler)
    watcher.run()
    signal.signal(signal.SIGINT, previous_sigint_handler)
  finally:
    ts_mon.close()

  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))

