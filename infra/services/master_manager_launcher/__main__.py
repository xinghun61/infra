#!/usr/bin/python
# Copyright 2015 Google Inc. All Rights Reserved.
# pylint: disable=F0401

"""Launch a master_manager script for every master on a host."""

# pragma: no cover

import argparse
import logging
import os
import socket
import subprocess
import sys

from infra.libs.gitiles import gitiles
from infra.libs.process_invocation import multiprocess
from infra.libs.service_utils import daemon
from infra.services.master_manager_launcher import desired_state_parser
from infra_libs import logs


SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
RUNPY = os.path.abspath(os.path.join(
  SCRIPT_DIR, os.pardir, os.pardir, os.pardir, 'run.py'))


def parse_args():
  parser = argparse.ArgumentParser(
      description='Launches master_manager for every master on a host. NOTE: '
                  'does not perform any action unless --prod is set.')
  parser.add_argument('build_dir', nargs='?',
      help='location of the tools/build directory')
  parser.add_argument('--hostname',
      default=socket.getfqdn(),
      help='override local hostname (currently %(default)s)')
  parser.add_argument('--json-file',
      help='load desired master state from a file on disk')
  parser.add_argument('--json-gitiles',
      help='load desired master state from a gitiles location')
  parser.add_argument('--netrc',
      help='location of the netrc file when connecting to gitiles')
  parser.add_argument('--command-timeout',
      help='apply a timeout in seconds to each master_manager process')
  parser.add_argument('--verify', action='store_true',
      help='verify the desired master state JSON is valid, then exit')
  parser.add_argument('--prod', action='store_true',
      help='actually perform actions instead of doing a dry run')
  parser.add_argument('--processes',
      default=16, type=int,
      help='maximum number of master_manager processes to run simultaneously '
           '(default %(default)d)')
  logs.add_argparse_options(parser)

  args = parser.parse_args()
  logs.process_argparse_options(args)

  if args.json_file and args.json_gitiles:
    parser.error('Can\'t specify --json-file and --json-gitiles simultaneously')

  if not args.json_gitiles and not args.json_file:
    parser.error('Must specify either --json-gitiles or --json-file.')

  if not args.verify:
    if not args.build_dir:
      parser.error('A build/ directory must be specified.')

  return args


def synthesize_master_manager_cmd(master_dict, hostname, prod=False):
  """Find the current desired state and synthesize a command for the master."""
  state = desired_state_parser.get_master_state(master_dict['states'])
  cmd = [
      RUNPY,
      'infra.tools.master_manager',
      master_dict['fulldir'],
      str(state['desired_state']),
      str(desired_state_parser.parse_transition_time(
          state['transition_time_utc'])),
      '--hostname', hostname,
      '--enable-gclient-sync',
      '--verbose',
  ]

  if prod:
    cmd.append('--prod')

  return cmd


def log_triggered_ignored(triggered, ignored, hostname):
  """Outputs for humans which masters will be managed and which won't."""
  if ignored:
    logging.info(
        '%d masters on host %s left unmanaged (no desired state section):\n%s',
        len(ignored), hostname, '\n'.join(ignored))

  triggered_master_string = '.'
  if triggered:
    triggered_master_string = ':\n'
  triggered_master_string += '\n'.join(m['dirname'] for m in triggered)
  logging.info(
      '%d masters managed for host %s%s',
      len(triggered), hostname, triggered_master_string)


def main():
  args = parse_args()

  if args.json_file:
    desired_state = desired_state_parser.load_desired_state_file(
        args.json_file)
  else:
    desired_state_data = gitiles.call_gitiles(
        args.json_gitiles, 'text', netrc_path=args.netrc)
    desired_state = desired_state_parser.parse_desired_state(desired_state_data)

  if args.verify:
    return 0  # File checks out, no need to continue.

  triggered, ignored = desired_state_parser.get_masters_for_host(
      desired_state, args.build_dir, args.hostname)
  log_triggered_ignored(triggered, ignored, args.hostname)

  commands = [
      synthesize_master_manager_cmd(m, args.hostname, prod=args.prod)
      for m in triggered
  ]

  if args.command_timeout:
    commands = [daemon.add_timeout(c, args.command_timeout) for c in commands]

  multiprocess.safe_map(subprocess.call, commands, args.processes)


if __name__ == '__main__':
  sys.exit(main())
