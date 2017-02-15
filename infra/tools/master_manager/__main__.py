#!/usr/bin/python
# Copyright 2015 Google Inc. All Rights Reserved.
# pylint: disable=F0401

"""Start, restart and shut down masters as needed."""

import argparse
import logging
import os
import re
import socket
import subprocess
import sys

from functools import partial

from infra.libs.buildbot import master
from infra.libs.service_utils import daemon
from infra.libs.service_utils import outer_loop
from infra.services.master_lifecycle import buildbot_state
from infra_libs import logs
from infra_libs import ts_mon


run_count = ts_mon.CounterMetric(
    'master_manager/run_count',
    'Count the number of state machine runs.',
    [ts_mon.StringField('result'), ts_mon.StringField('action')])


def parse_args(argv):
  parser = argparse.ArgumentParser(
      description='Manage the state of a buildbot master. NOTE: Does nothing '
                  'unless --prod is specified')
  parser.add_argument('directory', nargs='?',
      help='location of the master to manage')
  parser.add_argument('desired_state', nargs='?',
      choices=buildbot_state.STATES['desired_buildbot_state'],
      help='the desired state of the master')
  parser.add_argument('transition_time_utc', nargs='?', type=float,
      help='seconds since the UTC epoch to trigger the state')
  parser.add_argument('--list-all-states', action='store_true',
      help='list all states with their actions and exit')
  parser.add_argument('--builder-filter', action='append', default=[],
      help='appends a Python regular expression to the list of builder '
           'filters. By default, all builders count as building; if builder '
           'filters are supplied, only builders that match at least one filter '
           'will be counted.')
  parser.add_argument('--drain-timeout', metavar='SECONDS', type=int,
      default=buildbot_state.DEFAULT_DRAIN_TIMEOUT_SEC,
      help='sets the drain state timeout, in seconds.')
  parser.add_argument('--enable-gclient-sync', action='store_true',
      help='perform a gclient sync before every master start')
  parser.add_argument('--emergency-file',
      default='.stop_master_lifecycle',
      help='filename of the emergency stop file. if this file is found in the '
           'master directory, exit immediately')
  parser.add_argument('--hostname',
      default=socket.getfqdn(),
      help='override local hostname (currently %(default)s)')
  parser.add_argument('--prod', action='store_true',
      help='actually run commands instead of printing them.')
  parser.add_argument('--loop', action='store_true',
      help='repeatedly run the state machine. will not terminate unless killed')
  parser.add_argument('--loop-sleep-secs', type=int, default=5,
      help='how many seconds to wait between loop runs. default %(default)s')
  parser.add_argument('--connection-timeout', type=int, default=30,
      help='how many seconds to wait for a master http request before timing '
           'out.')
  outer_loop.add_argparse_options(parser)
  logs.add_argparse_options(parser)
  ts_mon.add_argparse_options(parser)

  parser.set_defaults(
    ts_mon_target_type='task',
    ts_mon_task_job_name='unset',  # Will be overwritten with master name.
    ts_mon_task_service_name='master_manager',
    ts_mon_flush_mode='manual',
  )

  args = parser.parse_args(argv)

  if not args.list_all_states:
    if not args.directory:
      parser.error('A master directory must be specified.')
    if not args.transition_time_utc:
      parser.error('A transition time must be specified.')

    if args.ts_mon_task_job_name == 'unset':
      abs_master_directory = os.path.abspath(args.directory)
      args.ts_mon_task_job_name = abs_master_directory.split('/')[-1]

    logs.process_argparse_options(args)
    ts_mon.process_argparse_options(args)

  return args


def master_hostname_is_valid(local_hostname, abs_master_directory, logger):
  master_hostname = master.get_mastermap_data(
      abs_master_directory)['fullhost']
  if master_hostname != local_hostname:  # pragma: no cover
    logger.error('%s does not match %s, aborting. use --hostname to override.',
        local_hostname, master_hostname)
    return False
  return True


def run_state_machine_pass(
    logger, matchlist, abs_master_directory, emergency_file, desired_state,
    transition_time_utc, enable_gclient_sync, prod, connection_timeout,
    hostname, builder_filters):
  if os.path.exists(os.path.join(
      abs_master_directory, emergency_file)):  # pragma: no cover
    logger.error('%s detected in %s, aborting!',
        emergency_file, abs_master_directory)
    run_count.increment(fields={'result': 'failure', 'action': 'none'})
    return 1

  if not master_hostname_is_valid(
      hostname, abs_master_directory, logger):  # pragma: no cover
    run_count.increment(fields={'result': 'failure', 'action': 'none'})
    return 1

  evidence = buildbot_state.collect_evidence(
      abs_master_directory,
      connection_timeout=connection_timeout,
      builder_filters=builder_filters)
  evidence['desired_buildbot_state'] = {
      'desired_state': desired_state,
      'transition_time_utc': transition_time_utc,
  }

  state, action_name, action_items = matchlist.execution_list(evidence)
  execution_list = list(
      master.convert_action_items_to_cli(
      action_items, abs_master_directory,
      enable_gclient=enable_gclient_sync))
  logger.info('%s: current state: %s', abs_master_directory, state)
  logger.info('%s: performing action: %s', abs_master_directory, action_name)

  if execution_list:  # pragma: no branch
    if prod:
      logger.info('production run, executing:')
    else:
      logger.info('dry run, not executing:')
    for cmd in execution_list:
      logger.info('*  %s (in %s)', cmd['cmd'], cmd['cwd'])
      if prod:
        try:
          with daemon.flock(cmd['lockfile']):
            subprocess.check_call(  # pragma: no branch
                [str(x) for x in cmd['cmd']],
                cwd=cmd['cwd'],
                close_fds=True)
        except daemon.LockAlreadyLocked:  # pragma: no cover
          logger.warn('  lock on %s could not be acquired, no action taken.',
              cmd['lockfile'])
  else:  # pragma: no cover
    logger.info('no action to be taken.')

  run_count.increment(fields={'result': 'success', 'action': action_name})
  return 0


def run(argv):
  args = parse_args(argv)

  logger = logging.getLogger(__name__)
  logs.add_handler(logger)

  matchlist = buildbot_state.construct_pattern_matcher(
      drain_timeout_sec=args.drain_timeout)

  if args.list_all_states:  # pragma: no cover
    matchlist.print_all_states()
    return 0

  abs_master_directory = os.path.abspath(args.directory)

  builder_filters = [re.compile(f) for f in args.builder_filter]
  state_machine = partial(run_state_machine_pass, logger,
        matchlist, abs_master_directory, args.emergency_file,
        args.desired_state, args.transition_time_utc, args.enable_gclient_sync,
        args.prod, args.connection_timeout, args.hostname, builder_filters)

  if args.loop:  # pragma: no cover
    loop_opts = outer_loop.process_argparse_options(args)
    outer_loop.loop(
        state_machine, lambda: args.loop_sleep_secs, **loop_opts)
  else:
    return state_machine()

  return 0  # pragma: no cover


def main():  # pragma: no cover
  ret = run(sys.argv[1:])
  ts_mon.flush()
  return ret


if __name__ == '__main__':
  sys.exit(main())
