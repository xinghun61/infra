#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Send system monitoring data to the timeseries monitoring API."""

import random
import time

import psutil

from infra.libs.service_utils import outer_loop
from infra.services.sysmon import puppet_metrics
from infra.services.sysmon import root_setup
from infra.services.sysmon import system_metrics
from infra_libs import ts_mon


class SysMon(outer_loop.Application):
  def add_argparse_options(self, parser):
    super(SysMon, self).add_argparse_options(parser)

    parser.add_argument(
        '--interval',
        default=10, type=int,
        help='time (in seconds) between sampling system metrics')
    parser.add_argument(
        '--root-setup',
        action='store_true',
        help='if this is set sysmon will run once to initialise configs in '
             '/etc and then exit immediately.  Used on GCE bots to bootstrap '
             'sysmon')

    parser.set_defaults(
        ts_mon_flush='manual',
    )

  def task(self):
    try:
      system_metrics.get_uptime()
      system_metrics.get_cpu_info()
      system_metrics.get_disk_info()
      system_metrics.get_mem_info()
      system_metrics.get_net_info()
      system_metrics.get_proc_info()
      puppet_metrics.get_puppet_summary()
    finally:
      ts_mon.flush()
    return True

  def sleep_timeout(self):
    return self.opts.interval

  def main(self, opts):
    if opts.root_setup:
      return root_setup.root_setup()

    # This returns a 0 value the first time it's called.  Call it now and
    # discard the return value.
    psutil.cpu_times_percent()

    # Wait a random amount of time before starting the loop in case sysmon is
    # started at exactly the same time on all machines.
    time.sleep(random.uniform(0, opts.interval))

    return super(SysMon, self).main(opts)


if __name__ == '__main__':
  SysMon().run()
