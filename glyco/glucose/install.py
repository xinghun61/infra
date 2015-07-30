# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import logging
import os
import sys

from glucose import util


LOGGER = logging.getLogger(__name__)


def has_valid_sha1(filename):
  """Verify the hash of a whl file created by Glyco.

  Args:
    filename (str): path to a whl file.

  Returns:
    matches (bool): true if the file content and the name match.
  """
  basename = os.path.split(filename)[-1]
  wheel_info = util.WHEEL_FILE_RE.match(basename)
  if not wheel_info:
    raise util.InvalidWheelFile('Invalid file name for wheel: %s'
                                % basename)
  if not wheel_info.group('build'):
    raise util.InvalidWheelFile('No hash could be found in the filename.\n'
                                'Has this file been generated with Glyco?\n'
                                '%s' % basename)
  claimed_sha = wheel_info.group('build').split('_')[1]

  with open(filename, 'rb') as f:
    digest = hashlib.sha1(f.read())
  actual_sha = digest.hexdigest()

  return actual_sha == claimed_sha


def install(args):
  """Install wheel files"""

  if not args.packages:
    print 'No packages have been provided on the command-line, doing nothing.'
    return

  if not args.install_dir:
    print >> sys.stderr, ('No destination directory specified, aborting. \n'
                          'Use the --install-dir option to specify it')
    return 2

  if not os.path.isdir(args.install_dir):
    os.mkdir(args.install_dir)


  all_valid = True
  for filename in args.packages:
    if not has_valid_sha1(filename):
      print >> sys.stderr, ("File content does not match hash for %s"
                            % filename)
      all_valid = False

  if not all_valid:
    print >> sys.stderr, ('Some file hashes do not match their content. '
                          'Aborting.')
    return 1

  with util.Virtualenv() as venv:
    cmd = (['pip', 'install', '--no-index', '--target', args.install_dir]
           + args.packages)
    LOGGER.debug('Running %s', ' '.join(cmd))
    venv.check_call(cmd)


def add_subparser(subparsers):
  """Add the 'install' command.

  Also add the 'lysis' command as a synonym (and pun).

  Args:
    subparsers: output of argparse.ArgumentParser.add_subparsers()
  """
  install_parser = subparsers.add_parser('install',
                                         help='Install wheel files to a local '
                                              'directory (synonym of lysis)')
  install_parser.set_defaults(command=install)

  # Add synonym just for the pun
  lysis_parser = subparsers.add_parser('lysis',
                                       help='Install wheel files to a local '
                                       'directory (synonym of install)')

  lysis_parser.set_defaults(command=install)

  for parser in (install_parser, lysis_parser):
    parser.add_argument('--install-dir', '-i',
                        help='Directory where to install packages')
    parser.add_argument('packages', metavar='PACKAGE', nargs='*',
                        help='Wheel files to install (path)')
