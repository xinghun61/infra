#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import signal
import socket
import sys

from infra_libs import experiments
from infra.services.service_manager import config_watcher
from infra.services.service_manager import root_setup

import infra_libs


class ServiceManager(infra_libs.BaseApplication):
  DESCRIPTION = ('Starts and stops machine-wide infra services with arguments '
                 'from config files')

  def add_argparse_options(self, parser):
    super(ServiceManager, self).add_argparse_options(parser)

    if sys.platform == 'win32':
      default_state_directory = 'C:\\chrome-infra\\service-state'
      default_config_directory = 'C:\\chrome-infra\\service-config'
      default_root_directory = 'C:\\infra-python'
      default_cloudtail_path = 'C:\\infra-python\\go\\bin\\cloudtail.exe'
    else:
      default_state_directory = '/var/run/infra-services'
      default_config_directory = '/etc/infra-services'
      default_root_directory = '/opt/infra-python'
      default_cloudtail_path = '/opt/infra-python/go/bin/cloudtail'

    parser.add_argument(
        '--state-directory',
        default=default_state_directory,
        help='directory to store PID files (default %(default)s)')
    parser.add_argument(
        '--config-directory',
        default=default_config_directory,
        help='directory to read JSON config files (default %(default)s)')
    parser.add_argument(
        '--root-directory',
        default=default_root_directory,
        help='directory where the service_manager package is deployed. If this '
             'package is updated the process will exit')

    parser.add_argument(
        '--config-poll-interval',
        default=10,
        help='how frequently (in seconds) to poll the config directory')
    parser.add_argument(
        '--service-poll-interval',
        default=10,
        help='how frequently (in seconds) to restart failed services')

    parser.add_argument(
        '--root-setup',
        action='store_true',
        help='if this is set service_manager will run once to initialise '
             'configs in /etc and then exit immediately.  Used on GCE bots to '
             'bootstrap service_manager')

    parser.add_argument(
        '--cloudtail-experiment-percent',
        type=int, default=100,
        help='Probability of tailing log files of started services to cloud '
             'logging using cloudtail (default %(default)s%%)')
    parser.add_argument(
        '--cloudtail-path',
        default=default_cloudtail_path,
        help='Path to the cloudtail binary (default %(default)s)')

    parser.set_defaults(
        ts_mon_target_type='task',
        ts_mon_task_service_name='service_manager',
        ts_mon_task_job_name=socket.getfqdn(),
    )

  def main(self, opts):
    if opts.root_setup:
      return root_setup.root_setup()

    cloudtail_active = experiments.is_active_for_host(
        'cloudtail', opts.cloudtail_experiment_percent)

    watcher = config_watcher.ConfigWatcher(
        opts.config_directory,
        opts.config_poll_interval,
        opts.service_poll_interval,
        opts.state_directory,
        opts.root_directory,
        opts.cloudtail_path if cloudtail_active else None)

    def sigint_handler(_signal, _frame):
      watcher.stop()

    previous_sigint_handler = signal.signal(signal.SIGINT, sigint_handler)
    watcher.run()
    signal.signal(signal.SIGINT, previous_sigint_handler)


if __name__ == '__main__':
  ServiceManager().run()

