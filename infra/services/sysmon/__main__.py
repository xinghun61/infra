#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Send system monitoring data to the timeseries monitoring API."""

import argparse
import os
import random
import sys
import time

import psutil

from infra.libs.service_utils import outer_loop
from infra_libs import ts_mon
from infra_libs import logs


cpu_time = ts_mon.FloatMetric('dev/cpu/time')

disk_free = ts_mon.GaugeMetric('dev/disk/free')
disk_total = ts_mon.GaugeMetric('dev/disk/total')

# inode counts are only available on Unix.
if os.name == 'posix':
  inodes_free = ts_mon.GaugeMetric('dev/inodes/free')
  inodes_total = ts_mon.GaugeMetric('dev/inodes/total')

mem_free = ts_mon.GaugeMetric('dev/mem/free')
mem_total = ts_mon.GaugeMetric('dev/mem/total')

net_up = ts_mon.GaugeMetric('dev/net/up')
net_down = ts_mon.GaugeMetric('dev/net/down')

proc_count = ts_mon.GaugeMetric('dev/proc/count')


def get_cpu_info():
  times = psutil.cpu_times_percent()
  for mode in ('user', 'system', 'idle'):
    cpu_time.set(getattr(times, mode), {'mode': mode})


def get_disk_info():
  disks = psutil.disk_partitions()
  for disk in disks:
    labels = {'path': disk.mountpoint}

    usage = psutil.disk_usage(disk.mountpoint)
    disk_free.set(usage.free, labels)
    disk_total.set(usage.total, labels)

    # inode counts are only available on Unix.
    if os.name == 'posix':
      stats = os.statvfs(disk.mountpoint)
      inodes_free.set(stats.f_favail, labels)
      inodes_total.set(stats.f_files, labels)


def get_mem_info():
  # We don't report mem.used because (due to virtual memory) it is not useful.
  mem = psutil.virtual_memory()
  mem_free.set(mem.available)
  mem_total.set(mem.total)


def get_net_info():
  nics = psutil.net_io_counters(pernic=True)
  for nic, counters in nics.iteritems():
    # This could easily be extended to track packets, errors, and drops.
    net_up.set(counters.bytes_sent, {'interface': nic})
    net_down.set(counters.bytes_recv, {'interface': nic})


def get_proc_info():
  procs = psutil.pids()
  proc_count.set(len(procs))


def parse_args(argv):
  p = argparse.ArgumentParser()

  p.add_argument(
      '--interval',
      default=10, type=int,
      help='time (in seconds) between sampling system metrics')

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

  def single_iteration():
    try:
      get_cpu_info()
      get_disk_info()
      get_mem_info()
      get_net_info()
      get_proc_info()
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
