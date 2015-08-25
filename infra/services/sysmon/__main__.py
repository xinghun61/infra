#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Send system monitoring data to the timeseries monitoring API."""

import argparse
import random
import sys
import time

import psutil

from infra.libs.service_utils import outer_loop
from infra.services.sysmon import puppet_metrics
from infra.services.sysmon import root_setup
from infra.services.sysmon import system_metrics
from infra_libs import logs
from infra_libs import ts_mon


def parse_args(argv):
  p = argparse.ArgumentParser()

  p.add_argument(
      '--interval',
      default=10, type=int,
      help='time (in seconds) between sampling system metrics')
  p.add_argument(
      '--root-setup',
      action='store_true',
      help='if this is set sysmon will run once to initialise configs in /etc '
           'and then exit immediately.  Used on GCE bots to bootstrap sysmon')

  logs.add_argparse_options(p)
  ts_mon.add_argparse_options(p)
  outer_loop.add_argparse_options(p)

  p.set_defaults(ts_mon_flush='manual')
  opts = p.parse_args(argv)

  logs.process_argparse_options(opts)
  ts_mon.process_argparse_options(opts)
  loop_opts = outer_loop.process_argparse_options(opts)

  return opts, loop_opts


def main(argv):
  opts, loop_opts = parse_args(argv)

  if opts.root_setup:
    return root_setup.root_setup()

  def single_iteration():
    try:
      system_metrics.get_cpu_info()
      system_metrics.get_disk_info()
      system_metrics.get_mem_info()
      system_metrics.get_net_info()
      system_metrics.get_proc_info()
      puppet_metrics.get_puppet_summary()
    finally:
      ts_mon.flush()
    return True

  # This returns a 0 value the first time it's called.  Call it now and discard
  # the return value.
  psutil.cpu_times_percent()

  # Wait a random amount of time before starting the loop in case sysmon is
  # started at exactly the same time on all machines.
  time.sleep(random.uniform(0, opts.interval))

  loop_results = outer_loop.loop(
      task=single_iteration,
      sleep_timeout=lambda: opts.interval,
      **loop_opts)

  return 0 if loop_results.success else 1


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
