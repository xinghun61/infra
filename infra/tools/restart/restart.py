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


def get_time():
  # TODO(hinoka): Also support times that are not now.
  restart_time = datetime.datetime.utcnow()
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


def commit(target, masters):
  """Commits the local CL via the CQ."""
  desc = 'Restarting masters %s' % ', '.join(masters)
  subprocess.check_call(
      ['git', 'commit', '--all', '--message', desc], cwd=target)
  LOGGER.info('Uploading to Rietveld and CQ.')
  subprocess.check_call(
      ['git', 'cl', 'upload', '-m', desc, '-t', desc,
       '--tbr-owners', '-c', '-f'], cwd=target)


def run(masters):
  """Restart all the masters in the list of masters."""
  # Step 1: Acquire a clean master state checkout.
  # This repo is too small to consider caching.
  master_state_dir = get_master_state_checkout()
  with get_master_state_checkout() as master_state_dir:
    master_state_json = os.path.join(
        master_state_dir, 'desired_master_state.json')
    restart_time = get_time()

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
    commit(master_state_dir, masters)
