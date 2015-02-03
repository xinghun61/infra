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


cpu_count = ts_mon.GaugeMetric('dev/cpu/count')
cpu_percent = ts_mon.FloatMetric('dev/cpu/usage')

# TODO(agable): Add a 'Units' field to Metrics so this can specify Bytes.
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


def main(argv):
  p = argparse.ArgumentParser()

  logs.add_argparse_options(p)
  ts_mon.add_argparse_options(p)
  args = p.parse_args(argv)
  logs.process_argparse_options(args)
  ts_mon.process_argparse_options(args)

  get_cpu_info()
  get_disk_info()
  get_mem_info()
  get_net_info()


if __name__ == '__main__':
  main(sys.argv[1:])
