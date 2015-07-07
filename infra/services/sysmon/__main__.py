#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Send system monitoring data to the timeseries monitoring API."""

import argparse
import os
import sys

import psutil

from infra.libs.service_utils import outer_loop
from infra_libs import ts_mon
from infra_libs import logs


cpu_count = ts_mon.GaugeMetric('dev/cpu/count')
cpu_user_percent = ts_mon.FloatMetric('dev/cpu/user')
cpu_system_percent = ts_mon.FloatMetric('dev/cpu/system')
cpu_idle_percent = ts_mon.FloatMetric('dev/cpu/idle')
cpu_total_percent = ts_mon.FloatMetric('dev/cpu/total')

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
  num_cores = psutil.cpu_count()
  cpu_count.set(num_cores)
  # Warning: blocking call for the duration of 'interval'.
  times_percents = psutil.cpu_times_percent(interval=1.0, percpu=True)
  total_percents = psutil.cpu_percent(percpu=True)  # uses same interval.
  # psutil guarantees that the return values when percpu=True always have
  # the same deterministic ordering, so we can rely on that here.
  for cpu in xrange(num_cores):
    # We only report user, system, and idle because others (such as nice) aren't
    # available on all platforms.
    cpu_user_percent.set(times_percents[cpu].user, {'core': cpu})
    cpu_system_percent.set(times_percents[cpu].system, {'core': cpu})
    cpu_idle_percent.set(times_percents[cpu].idle, {'core': cpu})
    cpu_total_percent.set(total_percents[cpu], {'core': cpu})


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

  # Set our own defaults (rather than outer_loop's "forever" and "infinity").
  # Our defaults are such that it will run only once and then exit.
  loop_opts = outer_loop.process_argparse_options(opts)
  if not loop_opts.get('duration'):
    loop_opts['duration'] = 0
  if not loop_opts.get('max_errors'):
    loop_opts['max_errors'] = 0

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

  loop_results = outer_loop.loop(
      task=single_iteration,
      sleep_timeout=lambda: opts.interval,
      **loop_opts)

  return 0 if loop_results.success else 1


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
