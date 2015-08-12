# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile


from infra.libs.time_functions import zulu


LOGGER = logging.getLogger(__name__)


class MasterNotFoundException(Exception):
  pass


def add_argparse_options(parser):
  parser.add_argument('masters', type=str, nargs='+', help='Master to restart.')
  parser.add_argument(
      '-m', '--minutes-in-future', default=15, type=int,
      help='how many minutes in the future to schedule the restart. '
           'use 0 for "now." default %(default)d')
  parser.add_argument('-b', '--bug', default=None, type=str,
                      help='Bug containing master restart request.')


def get_restart_time(delta):
  """Returns a zulu time string of when to restart a master, now + delta."""
  restart_time = datetime.datetime.utcnow() + delta
  return zulu.to_zulu_string(restart_time)


@contextlib.contextmanager
def get_master_state_checkout():
  target_dir = tempfile.mkdtemp()
  mm_repo = 'https://chrome-internal.googlesource.com/infradata/master-manager'
  try:
    LOGGER.info('Cloning %s into %s' % (mm_repo, target_dir))
    subprocess.call(['git', 'clone', mm_repo, target_dir])
    LOGGER.info('done')
    yield target_dir
  finally:
    shutil.rmtree(target_dir)


def commit(target, masters, bug):
  """Commits the local CL via the CQ."""
  desc = 'Restarting master(s) %s' % ', '.join(masters)
  if bug:
    desc = '%s\nBUG=%s' % (desc, bug)
  subprocess.check_call(
      ['git', 'commit', '--all', '--message', desc], cwd=target)
  LOGGER.info('Uploading to Rietveld and CQ.')
  subprocess.check_call(
      ['git', 'cl', 'upload', '-m', desc, '-t', desc,
       '--tbr-owners', '-c', '-f'], cwd=target)


def run(masters, delta, bug):
  """Restart all the masters in the list of masters.

    Schedules the restart for now + delta.
  """
  # Step 1: Acquire a clean master state checkout.
  # This repo is too small to consider caching.
  with get_master_state_checkout() as master_state_dir:
    master_state_json = os.path.join(
        master_state_dir, 'desired_master_state.json')
    restart_time = get_restart_time(delta)

    # Step 2: make modifications to the master state json.
    LOGGER.info('Reading %s' % master_state_json)
    with open(master_state_json, 'r') as f:
      master_state = json.load(f)
    LOGGER.info('Loaded')

    for master in masters:
      if master not in master_state:
        msg = '%s not found in master state' % master
        LOGGER.error(msg)
        raise MasterNotFoundException(msg)

      master_state[master].append({
          'desired_state': 'running', 'transition_time_utc': restart_time
      })

    LOGGER.info('Writing back to JSON file, %d new entries' % len(master_state))
    with open(master_state_json, 'w') as f:
      json.dump(
          master_state, f, sort_keys=True, indent=2, separators=(',', ':'))

    # Step 3: Send the patch to Rietveld and commit it via the CQ.
    LOGGER.info('Committing back into repository')
    commit(master_state_dir, masters, bug)
