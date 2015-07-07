#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Send buildbot master monitoring data to the timeseries monitoring API."""

import argparse
import socket
import sys
import urlparse

import requests

from infra.libs.buildbot import master
from infra.libs.service_utils import outer_loop
from infra.services.mastermon import pollers
from infra_libs import logs
from infra_libs import ts_mon


def parse_args(argv):
  p = argparse.ArgumentParser()

  group = p.add_mutually_exclusive_group(required=True)
  group.add_argument(
      '--url',
      help='URL of one buildbot master to monitor')
  group.add_argument('--build-dir',
      help='location of the tools/build directory. Used with --hostname to get '
      'the list of all buildbot masters on this host to monitor. Cannot be '
      'used with --url')

  p.add_argument('--hostname',
      default=socket.getfqdn(),
      help='override local hostname (currently %(default)s). Used with '
      '--build-dir to get the list of all buildbot masters on this host to '
      'monitor')
  p.add_argument(
      '--interval',
      default=300, type=int,
      help='time (in seconds) between sampling the buildbot master')

  logs.add_argparse_options(p)
  ts_mon.add_argparse_options(p)
  outer_loop.add_argparse_options(p)

  DEFAULT_ARG_VALUE = '(default)'

  p.set_defaults(
      ts_mon_flush='manual',
      ts_mon_target_type='task',
      ts_mon_task_service_name='mastermon',
      ts_mon_task_job_name=DEFAULT_ARG_VALUE,
  )
  opts = p.parse_args(argv)

  if opts.ts_mon_task_job_name == DEFAULT_ARG_VALUE:
    # The ts_mon job name defaults to either the hostname when monitoring all
    # masters on a host, or the name of the master extracted from the URL.
    if opts.build_dir:
      opts.ts_mon_task_job_name = opts.hostname
    else:
      parsed_url = urlparse.urlsplit(opts.url)
      path_components = [x for x in parsed_url.path.split('/') if x]
      if path_components:
        opts.ts_mon_task_job_name = path_components[-1]
      else:
        opts.ts_mon_task_job_name = parsed_url.netloc

  logs.process_argparse_options(opts)
  ts_mon.process_argparse_options(opts)
  loop_opts = outer_loop.process_argparse_options(opts)

  return opts, loop_opts


class MasterMonitor(object):
  up = ts_mon.BooleanMetric('buildbot/master/up')

  POLLER_CLASSES = [
    pollers.ClockPoller,
    pollers.BuildStatePoller,
    pollers.SlavesPoller,
  ]

  def __init__(self, url, name=None):
    if name is None:
      self._metric_fields = {}
    else:
      self._metric_fields = {'master': name}

    self._pollers = [
        cls(url, self._metric_fields) for cls in self.POLLER_CLASSES]

  def poll(self):
    for poller in self._pollers:
      if not poller.poll():
        self.up.set(False, fields=self._metric_fields)
        break
    else:
      self.up.set(True, fields=self._metric_fields)


def main(argv):
  opts, loop_opts = parse_args(argv)

  if opts.url:
    # Monitor a single master specified on the commandline.
    monitors = [MasterMonitor(opts.url)]
  else:
    # Query the mastermap and monitor all the masters on a host.
    monitors = [
        MasterMonitor(entry['buildbot_url'], entry['dirname'])
        for entry
        in master.get_mastermap_for_host(opts.build_dir, opts.hostname)]

  def single_iteration():
    try:
      for monitor in monitors:
        monitor.poll()
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
