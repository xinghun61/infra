#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Send buildbot master monitoring data to the timeseries monitoring API."""

import socket
import urlparse

from infra.libs.service_utils import outer_loop
from infra.services.mastermon import monitor
from infra_libs import ts_mon


class Application(outer_loop.Application):
  def __init__(self):
    super(Application, self).__init__()
    self.monitors = []

  def add_argparse_options(self, parser):
    super(Application, self).add_argparse_options(parser)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--url',
        help='URL of one buildbot master to monitor')
    group.add_argument('--build-dir',
        help='location of the tools/build directory. Used with --hostname to '
        'get the list of all buildbot masters on this host to monitor. Cannot '
        'be used with --url')

    parser.add_argument('--hostname',
        default=socket.getfqdn(),
        help='override local hostname (currently %(default)s). Used with '
        '--build-dir to get the list of all buildbot masters on this host to '
        'monitor')
    parser.add_argument('--interval',
        default=60, type=int,
        help='time (in seconds) between sampling the buildbot master')

    parser.set_defaults(
        ts_mon_flush='manual',
        ts_mon_target_type='task',
        ts_mon_task_service_name='mastermon',
        ts_mon_task_job_name='(default)',
    )

  def process_argparse_options(self, options):
    super(Application, self).process_argparse_options(options)

    if options.ts_mon_task_job_name == '(default)':
      # The ts_mon job name defaults to either the hostname when monitoring all
      # masters on a host, or the name of the master extracted from the URL.
      if options.build_dir:
        options.ts_mon_task_job_name = options.hostname
      else:
        parsed_url = urlparse.urlsplit(options.url)
        path_components = [x for x in parsed_url.path.split('/') if x]
        if path_components:
          options.ts_mon_task_job_name = path_components[-1]
        else:
          options.ts_mon_task_job_name = parsed_url.netloc

  def main(self, opts):
    if opts.url:
      # Monitor a single master specified on the commandline.
      self.monitors = [monitor.MasterMonitor(opts.url)]
    else:
      # Query the mastermap and monitor all the masters on a host.
      self.monitors = monitor.create_from_mastermap(
          opts.build_dir, opts.hostname)

    super(Application, self).main(opts)

  def sleep_timeout(self):
    return self.opts.interval

  def task(self):
    try:
      for mon in self.monitors:
        mon.poll()
    finally:
      ts_mon.flush()
    return True


if __name__ == '__main__':
  Application().run()
