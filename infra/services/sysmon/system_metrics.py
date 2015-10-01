# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno
import os
import logging

import psutil

from infra_libs import ts_mon
from infra_libs.ts_mon.common.metrics import MICROSECONDS_PER_SECOND


cpu_time = ts_mon.FloatMetric('dev/cpu/time')

disk_free = ts_mon.GaugeMetric('dev/disk/free')
disk_total = ts_mon.GaugeMetric('dev/disk/total')

# inode counts are only available on Unix.
if os.name == 'posix':  # pragma: no cover
  inodes_free = ts_mon.GaugeMetric('dev/inodes/free')
  inodes_total = ts_mon.GaugeMetric('dev/inodes/total')

mem_free = ts_mon.GaugeMetric('dev/mem/free')
mem_total = ts_mon.GaugeMetric('dev/mem/total')

START_TIME = int(psutil.boot_time() * MICROSECONDS_PER_SECOND)
net_up = ts_mon.CounterMetric('dev/net/bytes/up', start_time=START_TIME)
net_down = ts_mon.CounterMetric('dev/net/bytes/down', start_time=START_TIME)
net_err_up = ts_mon.CounterMetric('dev/net/err/up', start_time=START_TIME)
net_err_down = ts_mon.CounterMetric('dev/net/err/down', start_time=START_TIME)
net_drop_up = ts_mon.CounterMetric('dev/net/drop/up', start_time=START_TIME)
net_drop_down = ts_mon.CounterMetric('dev/net/drop/down', start_time=START_TIME)

proc_count = ts_mon.GaugeMetric('dev/proc/count')


def reset_metrics_for_unittest():
  metrics = [cpu_time, disk_free, disk_total, mem_free, mem_total, net_up,
             net_down, net_err_up, net_err_down, net_drop_up, net_drop_down,
             proc_count]
  if os.name == 'posix':  # pragma: no cover
    metrics.extend([inodes_free, inodes_total])

  for metric in metrics:
    metric.reset()


def get_cpu_info():
  times = psutil.cpu_times_percent()
  for mode in ('user', 'system', 'idle'):
    cpu_time.set(getattr(times, mode), {'mode': mode})


def get_disk_info(mountpoints=None):
  if mountpoints is None:
    mountpoints = [disk.mountpoint for disk in psutil.disk_partitions()]

  for mountpoint in mountpoints:
    labels = {'path': mountpoint}

    try:
      usage = psutil.disk_usage(mountpoint)
    except OSError as ex:
      if ex.errno == errno.ENOENT:
        # This happens on Windows when querying a removable drive that doesn't
        # have any media inserted right now.
        continue
      raise  # pragma: no cover

    disk_free.set(usage.free, labels)
    disk_total.set(usage.total, labels)

    # inode counts are only available on Unix.
    if os.name == 'posix':  # pragma: no cover
      stats = os.statvfs(mountpoint)
      inodes_free.set(stats.f_favail, labels)
      inodes_total.set(stats.f_files, labels)


def get_mem_info():
  # We don't report mem.used because (due to virtual memory) it is not useful.
  mem = psutil.virtual_memory()
  mem_free.set(mem.available)
  mem_total.set(mem.total)


def get_net_info():
  metric_counter_names = [
      (net_up, 'bytes_sent'),
      (net_down, 'bytes_recv'),
      (net_err_up, 'errout'),
      (net_err_down, 'errin'),
      (net_drop_up, 'dropout'),
      (net_drop_down, 'dropin'),
  ]

  nics = psutil.net_io_counters(pernic=True)
  for nic, counters in nics.iteritems():
    labels = {'interface': nic}
    for metric, counter_name in metric_counter_names:
      try:
        metric.set(getattr(counters, counter_name), labels)
      except ts_mon.MonitoringDecreasingValueError as ex:  # pragma: no cover
        # This normally shouldn't happen, but might if the network driver module
        # is reloaded, so log an error and continue instead of raising an
        # exception.
        logging.error(str(ex))


def get_proc_info():
  procs = psutil.pids()
  proc_count.set(len(procs))
