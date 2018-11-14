#!/usr/bin/env python
# Copyright 2017 The Chromium Authors. All rights reserved.
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
import zipfile

LOGGER = logging.getLogger(__name__)

try:
  import requests
except ImportError:
  print 'Run this in the infra virtualenv. See README.md'
  sys.exit(1)


TAGS_URL = 'https://api.github.com/repos/google/protobuf/releases/tags/'


def CIPD_TEMPLATE(cipd_platform):
  return 'infra/tools/protoc/%s' % (cipd_platform,)


def confirm(prompt, decline, exit_code=0):
  if not raw_input('%s (y/N): ' % prompt).lower().startswith('y'):
    print decline
    sys.exit(exit_code)


# list of (cipd_platform, github_version)
SUPPORTED_PLATFORMS = [
  ('linux-amd64', 'linux-x86_64'),
  ('mac-amd64', 'osx-x86_64'),
  # no 64-bit version, but 32-bit works on amd64 just fine.
  ('windows-386', 'win32'),
  ('windows-amd64', 'win32'),
]


FNULL = open(os.devnull, 'w')


def find_missing_platforms(vers):
  ret = []
  for platform, gh_vers in SUPPORTED_PLATFORMS:
    pkg = CIPD_TEMPLATE(platform)
    tag = 'protobuf_version:v'+vers
    p = subprocess.Popen(['cipd', 'resolve', pkg, '-version', tag],
                         stdout=FNULL, stderr=FNULL)
    if p.wait() != 0:
      status = 'Missing'
      ret.append((platform, gh_vers))
    else:
      status = 'Already uploaded'
    logging.info('  %s@%s -- %s.', pkg, tag, status)
  return ret


@contextlib.contextmanager
def do_download(gh_asset, for_windows):
  with tempfile.NamedTemporaryFile() as zip_file:
    url = gh_asset['browser_download_url']
    LOGGER.info('fetching %r', url)
    r = requests.get(url)
    if not r.ok:
      LOGGER.error('unable to download %r: %s', url, r.json()['message'])
      sys.exit(1)
    for chunk in r.iter_content(2048):
      zip_file.write(chunk)

    tdir = tempfile.mkdtemp()
    try:
      LOGGER.info('extracting zip')
      zf = zipfile.ZipFile(zip_file)
      for zi in zf.filelist:
        zf.extract(zi, tdir)
        if not for_windows and (zi.external_attr >> 16) & 0111:
          path = os.path.join(tdir, zi.filename)
          os.chmod(path, os.stat(path).st_mode | 0111)
      zf.extractall(tdir)

      yield tdir
    finally:
      def _log_err(func, path, exc_info):
        LOGGER.error('failed to delete path %r: %s', func, path,
                     exc_info=exc_info)
      shutil.rmtree(tdir, onerror=_log_err)


def repackage(gh_release, version, platform, gh_vers, dry_run, inspect):
  name = 'protoc-%s-%s.zip' % (version, gh_vers)
  for_windows = platform.startswith('windows')
  exe_sfx = '.exe' if for_windows else ''

  asset = None
  for a in gh_release['assets']:
    if a['name'] == name:
      asset = a
      break
  else:
    LOGGER.error('unable to find asset for %r', name)
    sys.exit(1)

  with do_download(asset, for_windows) as pkg_dir:
    LOGGER.info('rearranging ')
    bin_dir = os.path.join(pkg_dir, 'bin')
    shutil.move(os.path.join(bin_dir, 'protoc'+exe_sfx), pkg_dir)
    os.remove(os.path.join(pkg_dir, 'readme.txt'))
    os.rmdir(bin_dir)

    args = [
      'cipd', 'create',
      '-in', pkg_dir,
      '-name', CIPD_TEMPLATE(platform),
      '-tag', 'protobuf_version:v'+version,
    ]
    LOGGER.info('running %r%s', args, ' (dry run)' if dry_run else '')
    if inspect:
      confirm('Confirm %r' % pkg_dir, 'cipd create cancelled')
    if not dry_run:
      subprocess.check_call(args)


def get_gh_release(version):
  version = 'v'+version

  r = requests.get(TAGS_URL+version)
  if not r.ok:
    LOGGER.error('failed to get release data for %r: %s',
                 version, r.json()['message'])
    sys.exit(1)
  return r.json()


def main():
  p = argparse.ArgumentParser()
  p.add_argument('version', help='The version of protoc to grab, e.g. "3.0.0"')
  p.add_argument('--dry-run', action='store_true',
                 help='Do not actually do the upload.')
  p.add_argument('--confirm', action='store_true',
                 help=('Confirmation prompt before uploading to manually '
                       'inspect package.'))
  p.add_argument('--verbose', '-v', action='store_true', help='be noisy.')
  opts = p.parse_args()

  if opts.verbose:
    logging.basicConfig(level=logging.DEBUG)
  else:
    logging.basicConfig(level=logging.INFO)

  # can only run this tool on platforms which preserve the executable mode bit.
  if not sys.platform.startswith(('darwin', 'linux')):
    LOGGER.error('unsupported platform: %r', sys.platform)
    return 1

  missing = find_missing_platforms(opts.version)
  if not missing:
    LOGGER.info('All supported versions already uploaded.')
    return 0

  gh_release = get_gh_release(opts.version)
  print 'RELEASE NOTES:'
  print gh_release['body']
  print
  print 'VERSION: %s' % gh_release['name']
  for platform, _ in missing:
    print '  %s' % (platform,)

  confirm('Proceed?', 'update aborted')

  for platform, gh_vers in missing:
    repackage(gh_release, opts.version, platform, gh_vers,
              opts.dry_run, opts.confirm)
  return 0


if __name__ == '__main__':
  sys.exit(main())
