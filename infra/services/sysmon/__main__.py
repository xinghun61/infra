#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Send system monitoring data to the timeseries monitoring API."""

import argparse
import sys

import psutil

from infra.libs import logs
from infra.libs import ts_mon
from infra.libs.service_utils import outer_loop


cpu_count = ts_mon.GaugeMetric('dev/cpu/count')
cpu_percent = ts_mon.FloatMetric('dev/cpu/usage')

root_used = ts_mon.GaugeMetric('dev/disk/usage',
                               fields={'state': 'used', 'path': '/'})
root_free = ts_mon.GaugeMetric('dev/disk/usage',
                               fields={'state': 'free', 'path': '/'})

mem_used = ts_mon.GaugeMetric('dev/mem/usage', fields={'state': 'used'})
mem_free = ts_mon.GaugeMetric('dev/mem/usage', fields={'state': 'free'})

net_up = ts_mon.GaugeMetric('dev/net/traffic', fields={'direction': 'up'})
net_down = ts_mon.GaugeMetric('dev/net/traffic', fields={'direction': 'down'})


def get_cpu_info():
  cpu_count.set(psutil.cpu_count())
  # Warning: blocking call for the duration of 'interval'.
  cpu_percent.set(psutil.cpu_percent(interval=1.0))


def get_disk_info():
  disk = psutil.disk_usage('/')
  root_used.set(disk.used)
  root_free.set(disk.free)


def get_mem_info():
  mem = psutil.virtual_memory()
  mem_used.set(mem.used)
  mem_free.set(mem.available)


def get_net_info():
  net = psutil.net_io_counters()
  net_up.set(net.bytes_sent)
  net_down.set(net.bytes_recv)


def parse_args(argv):
  p = argparse.ArgumentParser()

  p.add_argument(
      '--interval',
      default=10, type=int,
      help='time (in seconds) between sampling system metrics')

  logs.add_argparse_options(p)
  ts_mon.add_argparse_options(p)
  outer_loop.add_argparse_options(p)
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
    get_cpu_info()
    get_disk_info()
    get_mem_info()
    get_net_info()
    return True

  loop_results = outer_loop.loop(
      task=single_iteration,
      sleep_timeout=lambda: opts.interval,
      **loop_opts)

  return 0 if loop_results.success else 1


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
