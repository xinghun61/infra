#!/usr/bin/env python
# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import contextlib
import logging
import os
import shutil
import subprocess
import sys
import tempfile

from install_cipd_packages import get_platform


BOOTSTRAP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BOOTSTRAP_DIR)

# Map of platform (or None, for all platforms) to CIPD package name.
CIPD_PKG_MAP = {
    'python': {
        None: 'infra/gae_sdk/python/all',
    },
    'go': {
        ('Linux', 'x86_64'): 'infra/gae_sdk/go/linux-amd64',
        ('Linux', 'x86'): 'infra/gae_sdk/go/linux-386',
        ('Darwin', 'x86_64'): 'infra/gae_sdk/go/mac-amd64',
    },
}


# Map of GAE SDK platform to its installation directory within "dest".
OUTDIR_NAME = {
    'python': 'google_appengine',
    'go': 'go_appengine',
}


# The path to CIPD executable. Note that Windows' "subprocess" will
# automatically append ".exe" to find the Windows executable.
CIPD_PATH = os.path.join(BASE_DIR, 'cipd', 'cipd')


class NoPackageException(Exception):
  pass


def get_cipd_config(plat):
  pkg_map = CIPD_PKG_MAP[plat]
  current_system, current_arch = get_platform()
  for s in ((current_system, current_arch), None):
    pkg_name = pkg_map.get(s)
    if pkg_name:
      return pkg_name, OUTDIR_NAME[plat]
  raise NoPackageException('No package for %s on %s/%s' % (
      plat, current_system, current_arch))


@contextlib.contextmanager
def tempdir():
  path = None
  try:
    path = tempfile.mkdtemp('get_appengine', dir=os.getcwd())
    yield path
  finally:
    if path:
      shutil.rmtree(path)


def install_gae_sdk(root_path, plat, version, dry_run):
  assert plat in {'python', 'go'}
  try:
    pkg_name, outdir_name = get_cipd_config(plat)
  except NoPackageException as e:
    logging.info('No packages identified: %s', e.message)
    return

  # If a version was specified, use that tag. Otherwise, use the "latest" ref.
  version = ('gae_sdk_version:%s' % (version,)) if version else ('latest')

  logging.info('Installing package %s @ %s', pkg_name, version)
  with tempdir() as tdir:
    # Build our CIPD package list.
    list_path = os.path.join(tdir, 'cipd_pkg_list.txt')
    with open(list_path, 'w') as fd:
      fd.write('%s %s' % (pkg_name, version))

    if dry_run:
      output = subprocess.check_output([
          CIPD_PATH,
          'resolve',
          pkg_name,
          '-version', version,
      ])
      print 'Resolve %s @ %s:\n%s' % (pkg_name, version, output)
      return

    # Create out output CIPD directory.
    outdir = os.path.join(root_path, outdir_name)
    cipd_init_dir = os.path.join(outdir, '.cipd')
    if os.path.isdir(outdir) and not os.path.isdir(cipd_init_dir):
      # Pre-CIPD installations will have a non-CIPD-managed version of this
      # directory. Destroy it so we can use CIPD.
      print 'Cleaning up pre-CIPD output directory: %s' % (outdir,)
      shutil.rmtree(outdir)
    if not os.path.isdir(outdir):
      os.makedirs(outdir)

    # Install the specified CIPD package.
    subprocess.check_call([
        CIPD_PATH,
        'ensure',
        '-root', outdir,
        '-list', list_path,
    ])


def main():
  parser = argparse.ArgumentParser(prog='python -m %s' % __package__)
  parser.add_argument('-v', '--verbose', action='store_true')
  parser.add_argument(
      '-g', '--go', action='store_true', help='Defaults to python SDK')
  parser.add_argument(
      '-d', '--dest', default=os.path.dirname(BASE_DIR), help='Output')
  parser.add_argument('--version', help='Specify which version to fetch')
  parser.add_argument('--dry-run', action='store_true', help='Do not download')
  options = parser.parse_args()

  if options.verbose:
    logging.getLogger().setLevel(logging.DEBUG)

  plat = ('go') if options.go else ('python')
  return install_gae_sdk(
      os.path.abspath(options.dest), plat, options.dry_run, options.version)


if __name__ == '__main__':
  logging.basicConfig(level=logging.ERROR)
  sys.exit(main())
