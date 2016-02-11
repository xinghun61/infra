# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime
import distutils.util
import json
import logging
import os
import pytz
import re
import shutil
import subprocess
import sys
import tempfile


from infra_libs.time_functions import zulu
from infra.services.master_lifecycle import buildbot_state
from infra.services.master_manager_launcher import desired_state_parser


LOGGER = logging.getLogger(__name__)

MM_REPO = 'https://chrome-internal.googlesource.com/infradata/master-manager'


class MasterNotFoundException(Exception):
  pass


def add_argparse_options(parser):
  parser.add_argument(
      'masters', type=str, nargs='+',
      help='Master(s) to restart. "master." prefix can be omitted.')
  parser.add_argument(
      '-m', '--minutes-in-future', default=15, type=int,
      help='how many minutes in the future to schedule the restart. '
           'use 0 for "now." default %(default)d')
  parser.add_argument(
      '--eod', action='store_true',
      help='schedules restart for 6:30PM Google Standard Time.')
  parser.add_argument('-b', '--bug', default=None, type=str,
                      help='Bug containing master restart request.')
  parser.add_argument('-r', '--reviewer', action='append', type=str,
                      help=(
                          'Reviewer to TBR the CL to. If not specified, '
                          'chooses a random reviewer from OWNERS file'))
  parser.add_argument(
      '-f', '--force', action='store_true',
      help='don\'t ask for confirmation, just commit')
  parser.add_argument(
      '-n', '--no-commit', action='store_true',
      help='update the file, but refrain from performing the actual commit')
  parser.add_argument(
      '-s', '--desired-state', default='running',
      choices=buildbot_state.STATES['desired_buildbot_state'],
      help='which desired state to put the buildbot master in '
           '(default %(default)s)')


def get_restart_time_eod():
  gst_now = datetime.datetime.now(pytz.timezone("America/Los_Angeles"))
  if gst_now.hour > 18 or (gst_now.hour == 18 and gst_now.minute > 30):
    # next 6:30PM is tomorrow
    gst_now += datetime.timedelta(days=1)
  gst_now = gst_now.replace(hour=18, minute=30, second=0, microsecond=0)
  return gst_now.astimezone(pytz.UTC).replace(tzinfo=None)


def get_restart_time_delta(mins):
  return datetime.datetime.utcnow() + datetime.timedelta(minutes=mins)


@contextlib.contextmanager
def get_master_state_checkout():
  target_dir = tempfile.mkdtemp()
  try:
    LOGGER.info('Cloning %s into %s' % (MM_REPO, target_dir))
    subprocess.call(['git', 'clone', MM_REPO, target_dir])
    LOGGER.info('done')
    yield target_dir
  finally:
    shutil.rmtree(target_dir)


def commit(
    target, masters, reviewers, bug, restart_time, restart_time_str, force,
    no_commit, desired_state):
  """Commits the local CL via the CQ."""
  if desired_state == 'running':
    action = 'Restarting'
  else:
    action = desired_state.title() + 'ing'
  desc = '%s master(s) %s\n' % (
      action, ', '.join(masters))
  if bug:
    desc += '\nBUG=%s' % bug
  if reviewers:
    desc += '\nTBR=%s' % ', '.join(reviewers)
  subprocess.check_call(
      ['git', 'commit', '--all', '--message', desc], cwd=target)

  delta = restart_time - datetime.datetime.utcnow()

  print
  print '%s the following masters in %d minutes (%s)' % (
      action, delta.total_seconds() / 60, restart_time_str)
  for master in sorted(masters):
    print '  %s' % master
  print

  print "This will upload a CL for master_manager.git, TBR an owner, and "
  if no_commit:
    print "wait for you to manually commit."
  else:
    print "commit the CL through the CQ."
  print



  if not force:
    if no_commit:
      print 'Upload CL? (will not set CQ bit) [Y/n]:',
    else:
      print 'Commit? [Y/n]:',
    input_string = raw_input()
    if input_string != '' and not distutils.util.strtobool(input_string):
      print 'Aborting.'
      return

  print 'To cancel, edit desired_master_state.json in %s.' % MM_REPO
  print

  LOGGER.info('Uploading to Rietveld and CQ.')
  upload_cmd = [
      'git', 'cl', 'upload',
      '-m', desc,
      '-t', desc, # Title becomes the message of CL. TBR and BUG must be there.
      '-f',
  ]
  if not reviewers:
    upload_cmd.append('--tbr-owners')
  if not no_commit:
    upload_cmd.append('-c')
  else:
    LOGGER.info('CQ bit not set, please commit manually. (--no-commit)')
  subprocess.check_call(upload_cmd, cwd=target)


def run(masters, restart_time, reviewers, bug, force, no_commit,
        desired_state):
  """Restart all the masters in the list of masters.

  Schedules the restart for restart_time.

  Args:
    masters - a list(str) of masters to restart
    restart_time - a datetime in UTC of when to restart them
    reviewers - a list(str) of reviewers for the CL (may be empty)
    bug - an integer bug number to include in the review or None
    force - a bool which causes commit not to prompt if true
    no_commit - doesn't set the CQ bit on upload
    desired_state - nominally 'running', picks which desired_state
                    to put the buildbot in
  """
  # Step 1: Acquire a clean master state checkout.
  # This repo is too small to consider caching.
  with get_master_state_checkout() as master_state_dir:
    master_state_json = os.path.join(
        master_state_dir, 'desired_master_state.json')

    # Step 2: make modifications to the master state json.
    LOGGER.info('Reading %s' % master_state_json)
    with open(master_state_json, 'r') as f:
      desired_master_state = json.load(f)
    LOGGER.info('Loaded')

    # Validate the current master state file.
    try:
      desired_state_parser.validate_desired_master_state(desired_master_state)
    except desired_state_parser.InvalidDesiredMasterState:
      LOGGER.exception("Failed to validate current master state JSON.")
      return 1

    master_states = desired_master_state.get('master_states', {})
    entries = 0
    restart_time_str = zulu.to_zulu_string(restart_time)
    for master in masters:
      if not master.startswith('master.'):
        master = 'master.%s' % master
      if master not in master_states:
        msg = '%s not found in master state' % master
        LOGGER.error(msg)
        raise MasterNotFoundException(msg)

      master_states.setdefault(master, []).append({
          'desired_state': desired_state,
          'transition_time_utc': restart_time_str,
      })
      entries += 1

    LOGGER.info('Writing back to JSON file, %d new entries' % (entries,))
    desired_state_parser.write_master_state(
        desired_master_state, master_state_json)

    # Step 3: Send the patch to Rietveld and commit it via the CQ.
    LOGGER.info('Committing back into repository')
    commit(master_state_dir, masters, reviewers, bug, restart_time,
           restart_time_str, force, no_commit, desired_state)
