# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Removes a file or directory recursively.

Optionally, can be configured to try and remove it as root to handle cases where
the target contains root-owned files.
"""

import argparse
import logging
import os
import subprocess
import sys

import infra_libs
import infra_libs.logs


# Path to the "__main__.py" scirpt.
SELF = os.path.abspath(__file__)


# Sentinel environment to prevent infinite reexecution.
_ENV_TRY_AS_ROOT = 'INFRA_TOOLS_RMTREE_TRYING_AS_ROOT'


# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
LOGGER = logging.getLogger(__name__)


def _can_try_as_root():
  # If we're running on Windows, we don't support escalation.
  if sys.platform == 'win32':
    return False

  # If our sentinel is set, that means that this execution was a try-as-root
  # execution, and we should not try again lest we recurse.
  if _ENV_TRY_AS_ROOT in os.environ:
    return False

  # If we're already root, then we don't need to try again as root.
  if os.geteuid() == 0:
    return False

  return True


def main(argv):
  parser = argparse.ArgumentParser('rmtree')
  parser.add_argument('--try-as-root', action='store_true',
      help='If true, try and use elevate permissions prior to deleting the '
           'target. Is elevation fails, proceed as current user.')
  parser.add_argument('targets', nargs='*',
      help='The target file or directory to remove.')

  infra_libs.logs.add_argparse_options(parser)
  args = parser.parse_args(argv)
  infra_libs.logs.process_argparse_options(args)

  if args.try_as_root and _can_try_as_root():
    # Set the sentinel so we don't infinitely recurse.
    env = os.environ.copy()
    env[_ENV_TRY_AS_ROOT] = '1'

    # Execute the same command with "sudo". Will return non-zero if there was
    # an error, or if "sudo" could not be executed without a password.
    cmd = ['sudo', '-n', sys.executable, SELF] + argv
    LOGGER.debug('(--try-as-root) Escalating: %r', cmd)
    rc = subprocess.call(cmd, env=env)
    if rc == 0:
      return 0

    LOGGER.info('(--try-as-root) Failed to execute as root (%d); trying as '
                'current user.', rc)

  for target in args.targets:
    LOGGER.info('Removing target: %r', target)
    infra_libs.rmtree(target)

  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
