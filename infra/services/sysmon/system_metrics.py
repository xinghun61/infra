# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno
import os

import psutil

from infra_libs import ts_mon


cpu_time = ts_mon.FloatMetric('dev/cpu/time')

disk_free = ts_mon.GaugeMetric('dev/disk/free')
disk_total = ts_mon.GaugeMetric('dev/disk/total')

# inode counts are only available on Unix.
if os.name == 'posix':  # pragma: no cover
  inodes_free = ts_mon.GaugeMetric('dev/inodes/free')
  inodes_total = ts_mon.GaugeMetric('dev/inodes/total')

mem_free = ts_mon.GaugeMetric('dev/mem/free')
mem_total = ts_mon.GaugeMetric('dev/mem/total')

net_up = ts_mon.GaugeMetric('dev/net/up')
net_down = ts_mon.GaugeMetric('dev/net/down')

proc_count = ts_mon.GaugeMetric('dev/proc/count')


def reset_metrics_for_unittest():
  metrics = [cpu_time, disk_free, disk_total, mem_free, mem_total, net_up,
             net_down, proc_count]
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
  nics = psutil.net_io_counters(pernic=True)
  for nic, counters in nics.iteritems():
    # This could easily be extended to track packets, errors, and drops.
    net_up.set(counters.bytes_sent, {'interface': nic})
    net_down.set(counters.bytes_recv, {'interface': nic})


def get_proc_info():
  procs = psutil.pids()
  proc_count.set(len(procs))
