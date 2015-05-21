#!/usr/bin/python
# Copyright 2015 Google Inc. All Rights Reserved.
# pylint: disable=F0401

"""Start, restart and shut down masters as needed."""

import argparse
import logging
import os
import socket
import subprocess
import sys

from functools import partial

from infra.libs.buildbot import master
from infra.libs.service_utils import daemon
from infra.libs.service_utils import outer_loop
from infra.services.master_lifecycle import buildbot_state
from infra_libs import logs


def parse_args():  # pragma: no cover
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

  args = parser.parse_args()
  logs.process_argparse_options(args)

  if not args.list_all_states:
    if not args.directory:
      parser.error('A master directory must be specified.')
    if not args.transition_time_utc:
      parser.error('A transition time must be specified.')
    if not args.desired_state:
      parser.error('A desired state must be specified.')
  return args


def master_hostname_is_valid(local_hostname, abs_master_directory, logger):
  master_hostname = master.get_mastermap_data(
      abs_master_directory)['fullhost']
  if master_hostname != local_hostname:
    logger.error('%s does not match %s, aborting. use --hostname to override.',
        local_hostname, master_hostname)
    return False
  return True


def run_state_machine_pass(
    logger, matchlist, abs_master_directory, emergency_file, desired_state,
    transition_time_utc, enable_gclient_sync, prod, connection_timeout,
    hostname):
  # pragma: no cover
  if os.path.exists(os.path.join(abs_master_directory, emergency_file)):
    logger.error('%s detected in %s, aborting!',
        emergency_file, abs_master_directory)
    return 1

  if not master_hostname_is_valid(hostname, abs_master_directory, logger):
    return 1

  evidence = buildbot_state.collect_evidence(
      abs_master_directory, connection_timeout=connection_timeout)
  evidence['desired_buildbot_state'] = {
      'desired_state': desired_state,
      'transition_time_utc': transition_time_utc,
  }

  state, action_name, action_items = matchlist.execution_list(evidence)
  execution_list = list(
      master.convert_action_items_to_cli(
      action_items, abs_master_directory,
      enable_gclient=enable_gclient_sync))
  logger.info('current state: %s', state)
  logger.info('performing action: %s', action_name)

  if execution_list:
    if prod:
      logger.info('production run, executing:')
    else:
      logger.info('dry run, not executing:')
    for cmd in execution_list:
      logger.info('*  %s (in %s)', cmd['cmd'], cmd['cwd'])
      if prod:
        try:
          with daemon.flock(cmd['lockfile']):
            subprocess.check_call(
                [str(x) for x in cmd['cmd']],
                cwd=cmd['cwd'],
                close_fds=True)
        except daemon.LockAlreadyLocked:
          logger.warn('  lock on %s could not be acquired, no action taken.',
              cmd['lockfile'])
  else:
    logger.info('no action to be taken.')
  return 0


def main():  # pragma: no cover
  args = parse_args()
  matchlist = buildbot_state.construct_pattern_matcher()
  logger = logging.getLogger(__name__)

  if args.list_all_states:
    matchlist.print_all_states()
    return 0

  abs_master_directory = os.path.abspath(args.directory)

  state_machine = partial(run_state_machine_pass, logger,
        matchlist, abs_master_directory, args.emergency_file,
        args.desired_state, args.transition_time_utc, args.enable_gclient_sync,
        args.prod, args.connection_timeout, args.hostname)

  if args.loop:
    loop_opts = outer_loop.process_argparse_options(args)
    outer_loop.loop(
        state_machine, lambda: args.loop_sleep_secs, **loop_opts)
  else:
    return state_machine()

  return 0


if __name__ == '__main__':  # pragma: no cover
  sys.exit(main())
