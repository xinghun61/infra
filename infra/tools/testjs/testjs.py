# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Testable functions for Testjs."""

import Queue
import contextlib
import logging
import multiprocessing
import os
import psutil
import random
import subprocess
import sys
import threading
import time

from infra.path_hacks.utils import full_infra_path


LOGGER = logging.getLogger(__name__)

NODE_PATH = os.path.join(full_infra_path, 'node', 'node.py')
KARMA_PATH = os.path.join(
    full_infra_path, 'appengine', 'third_party', 'npm_modules', 'node_modules',
    'karma', 'bin', 'karma')

LOCK_LOCATION = '/tmp/.X%d-lock'


class XvfbFailed(Exception):
  pass


def add_argparse_options(parser):
  """Define command-line arguments."""
  parser.add_argument('target', nargs='+', help='Path to root directory.')


def pid_matches(our_pid, display):
  LOGGER.info('Our pid: %s', our_pid)
  with open(LOCK_LOCATION % display) as f:
    their_pid = int(f.read().strip())
    LOGGER.info('Their pid: %s', their_pid)
  return our_pid == their_pid


@contextlib.contextmanager
def get_display():
  """Run Xvfb and return the display.  Linux2 only."""
  display = random.choice(range(100, 1000))
  while os.path.exists(LOCK_LOCATION % display):  # pragma: no cover
    display = random.choice(range(100, 1000))

  cmd = ['Xvfb', ':%d' % display, '-screen', '0', '1024x768x24', '-ac']
  LOGGER.info('Launching Xvfb')
  proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  while True:   # pragma: no branch
    # Poll loop to wait until Xvfb launched correctly.
    returncode = proc.poll()
    if returncode is not None:  # pragma: no cover
      # Process exited, this shouldn't happen.
      out, err = proc.communicate()
      LOGGER.error('stdout: %s' % out)
      LOGGER.error('stderr: %s' % err)
      LOGGER.error('Xvfb did not start, returncode: %s.', returncode)
      raise XvfbFailed()

    if not os.path.exists(LOCK_LOCATION % display):  # pragma: no cover
      # Process is running, but probably not ready.
      LOGGER.debug(
          'Lock file %s does not exist yet...' % (LOCK_LOCATION % display))
      time.sleep(0.01)
      continue  # Wait for Xvfb to start...

    # Check PID matches.
    if not pid_matches(proc.pid, display):  # pragma: no cover
      # Whoa something weird happened.
      LOGGER.error('Started process (%s) does not match pid file' % proc.pid)
      raise XvfbFailed()

    break  # yay.

  LOGGER.info('Successfully started Xvfb on display :%d' % display)
  yield ':%d' % display
  LOGGER.info('Killing Xvfb')
  proc.kill()
  LOGGER.info('Killed Xvfb')


def test_karma(target, chrome_bin, display):
  env = os.environ.copy()
  # TODO(hinoka): Figure out how to package the chrome sandbox.
  env['CHROME_DEVEL_SANDBOX'] = ''
  env['CHROME_BIN'] = chrome_bin
  if display:  # pragma: no branch
    env['DISPLAY'] = display
  cmd = [
      sys.executable, NODE_PATH, '--', KARMA_PATH, 'start', '--single-run']
  return subprocess.call(cmd, env=env, cwd=target)
