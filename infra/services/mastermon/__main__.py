#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Send buildbot master monitoring data to the timeseries monitoring API."""

import argparse
import sys

import requests

from infra.libs.service_utils import outer_loop
from infra.services.mastermon import pollers
from infra_libs import logs
from infra_libs import ts_mon


def parse_args(argv):
  p = argparse.ArgumentParser()

  p.add_argument(
      '--url',
      required=True,
      help='URL of the buildbot master to monitor')
  p.add_argument(
      '--interval',
      default=60, type=int,
      help='time (in seconds) between sampling the buildbot master')

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

  poller_classes = [
    pollers.ClockPoller,
    pollers.BuildStatePoller,
    pollers.SlavesPoller,
  ]

  poller_objects = [cls(opts.url) for cls in poller_classes]

  up = ts_mon.BooleanMetric('master/up')

  def single_iteration():
    for poller in poller_objects:
      if not poller.poll():
        up.set(False)
        break
    else:
      up.set(True)

    ts_mon.flush()
    return True

  loop_results = outer_loop.loop(
      task=single_iteration,
      sleep_timeout=lambda: opts.interval,
      **loop_opts)

  return 0 if loop_results.success else 1


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
