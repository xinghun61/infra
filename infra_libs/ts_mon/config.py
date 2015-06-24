# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import socket
import sys
import urlparse
import re

from infra_libs.ts_mon import interface
from infra_libs.ts_mon import monitors
from infra_libs.ts_mon import standard_metrics
from infra_libs.ts_mon import targets


def load_machine_config(filename):
  if not os.path.exists(filename):
    logging.info('Configuration file does not exist, ignoring: %s', filename)
    return {}

  try:
    with open(filename) as fh:
      return json.load(fh)
  except Exception:
    logging.error('Configuration file couldn\'t be read: %s', filename)
    raise


def add_argparse_options(parser):
  """Add monitoring related flags to a process' argument parser.

  Args:
    parser (argparse.ArgumentParser): the parser for the main process.
  """
  parser = parser.add_argument_group('Timeseries Monitoring Options')
  parser.add_argument(
      '--ts-mon-config-file',
      default='/etc/chrome-infra/ts-mon.json',
      help='path to a JSON config file that contains suitable values for '
           '"endpoint" and "credentials" for this machine. This config file is '
           'intended to be shared by all processes on the machine, as the '
           'values depend on the machine\'s position in the network, IP '
           'whitelisting and deployment of credentials. (default: %(default)s)')
  parser.add_argument(
      '--ts-mon-endpoint',
      help='url (including file://, pubsub://project/topic) to post monitoring '
           'metrics to. If set, overrides the value in --ts-mon-config-file')
  parser.add_argument(
      '--ts-mon-credentials',
      help='path to a pkcs8 json credential file. If set, overrides the value '
           'in --ts-mon-config-file')
  parser.add_argument(
      '--ts-mon-flush',
      choices=('all', 'manual', 'auto'), default='auto',
      help=('metric push behavior: all (send every metric individually), '
            'manual (only send when flush() is called), or auto (send '
            'automatically every --ts-mon-flush-interval-secs seconds). '
            '(default: %(default)s)'))
  parser.add_argument(
      '--ts-mon-flush-interval-secs',
      type=int,
      default=60,
      help=('automatically push metrics on this interval if '
            '--ts-mon-flush=auto.'))

  parser.add_argument(
      '--ts-mon-target-type',
      choices=('device', 'task'),
      default='device',
      help='the type of target that is being monitored ("device" or "task").'
           ' (default: %(default)s)')

  fqdn = socket.getfqdn()  # foo-[a|m]N.[chrome|golo].chromium.org
  host = fqdn.split('.')[0]  # foo-[a|m]N
  parser.add_argument(
      '--ts-mon-device-hostname',
      default=host,
      help='name of this device, (default: %(default)s')
  try:
    region = fqdn.split('.')[1]  # [chrome|golo]
  except IndexError:
    region = ''
  parser.add_argument(
      '--ts-mon-device-region',
      default=region,
      help='name of the region this devices lives in. (default: %(default)s)')
  try:
    # Regular expression that matches the vast majority of our host names.
    # Matches everything of the form 'masterN', 'masterNa', and 'foo-xN'.
    network = re.match(r'^([\w-]*?-[acm]|master)(\d+)a?$', host).group(2)  # N
  except AttributeError:
    network = ''
  parser.add_argument(
      '--ts-mon-device-network',
      default=network,
      help='name of the network this device is connected to. '
           '(default: %(default)s)')

  parser.add_argument(
      '--ts-mon-task-service-name',
      help='name of the service being monitored')
  parser.add_argument(
      '--ts-mon-task-job-name',
      help='name of this job instance of the task')
  parser.add_argument(
      '--ts-mon-task-region',
      default=region,
      help='name of the region in which this task is running '
           '(default: %(default)s)')
  parser.add_argument(
      '--ts-mon-task-hostname',
      default=host,
      help='name of the host on which this task is running '
           '(default: %(default)s)')
  parser.add_argument(
      '--ts-mon-task-number', type=int, default=0,
      help='number (e.g. for replication) of this instance of this task '
           '(default: %(default)s)')


def process_argparse_options(args):
  """Process command line arguments to initialize the global monitor.

  Also initializes the default target if sufficient arguments are supplied.
  If they aren't, all created metrics will have to supply their own target.
  This is generally a bad idea, as many libraries rely on the default target
  being set up.

  Starts a background thread to automatically flush monitoring metrics if not
  disabled by command line arguments.

  Args:
    args (argparse.Namespace): the result of parsing the command line arguments
  """

  # Parse the config file if it exists.
  config = load_machine_config(args.ts_mon_config_file)
  endpoint = config.get('endpoint', '')
  credentials = config.get('credentials', '')

  # Command-line args override the values in the config file.
  if args.ts_mon_endpoint:
    endpoint = args.ts_mon_endpoint
  if args.ts_mon_credentials:
    credentials = args.ts_mon_credentials

  if endpoint.startswith('file://'):
    interface.state.global_monitor = monitors.DiskMonitor(
        endpoint[len('file://'):])
  elif credentials:
    if endpoint.startswith('pubsub://'):
      url = urlparse.urlparse(endpoint)
      project = url.netloc
      topic = url.path.strip('/')
      interface.state.global_monitor = monitors.PubSubMonitor(
          credentials, project, topic)
    else:
      interface.state.global_monitor = monitors.ApiMonitor(
          credentials, endpoint)
  else:
    logging.error('Monitoring is disabled because --ts-mon-credentials was not '
                  'set')
    interface.state.global_monitor = monitors.NullMonitor()

  if args.ts_mon_target_type == 'device':
    interface.state.default_target = targets.DeviceTarget(
        args.ts_mon_device_region,
        args.ts_mon_device_network,
        args.ts_mon_device_hostname)
  if args.ts_mon_target_type == 'task':  # pragma: no cover
    # Reimplement ArgumentParser.error, since we don't have access to the parser
    if not args.ts_mon_task_service_name:
      print >> sys.stderr, ('Argument --ts-mon-task-service-name must be '
                            'provided when the target type is "task".')
      sys.exit(2)
    if not args.ts_mon_task_job_name:  # pragma: no cover
      print >> sys.stderr, ('Argument --ts-mon-task-job-name must be provided '
                            'when the target type is "task".')
      sys.exit(2)
    interface.state.default_target = targets.TaskTarget(
        args.ts_mon_task_service_name,
        args.ts_mon_task_job_name,
        args.ts_mon_task_region,
        args.ts_mon_task_hostname,
        args.ts_mon_task_number)

  interface.state.flush_mode = args.ts_mon_flush

  if args.ts_mon_flush == 'auto':
    interface.state.flush_thread = interface._FlushThread(
        args.ts_mon_flush_interval_secs)
    interface.state.flush_thread.start()

  standard_metrics.init()

