#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Send system monitoring data to the timeseries monitoring API."""

import random
import time

import psutil

from infra.libs.service_utils import outer_loop
from infra.services.sysmon import android_device_metrics
from infra.services.sysmon import cipd_metrics
from infra.services.sysmon import puppet_metrics
from infra.services.sysmon import root_setup
from infra.services.sysmon import system_metrics
from infra_libs import ts_mon


class SysMon(outer_loop.Application):
  def __init__(self):
    # make sure we call our super's init
    super(SysMon, self).__init__()

    # SysMon.task is called every minute we want to collect some metrics
    # (e.g. os_info) only once per hour, so here we count the minutes within
    # the hour
    #
    # NB: the guarantee for each call being a minute comes from
    #  chrome_infra/manifests/sysmon.pp in the puppet repo
    self._minute_count = 0

  def count_minute(self):
    """ should be called at the end of each call to self.task """
    # mark that we were called
    self._minute_count += 1

    # roll over each day-ish, 60 minutes * 24 hours
    self._minute_count %= 60 * 24

  def is_hour(self):
    """ check if this call is on the hour """
    return self._minute_count % 60 == 0

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
      if self.is_hour():
        # collect once per hour
        system_metrics.get_os_info()
      else:
        # clear on all other minutes
        system_metrics.clear_os_info()
      puppet_metrics.get_puppet_summary()
      cipd_metrics.get_cipd_summary()
      android_device_metrics.get_device_statuses()
      system_metrics.get_unix_time() # must be the last in the list

    finally:
      ts_mon.flush()
      self.count_minute()
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
