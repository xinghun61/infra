#!/usr/bin/env python
# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import contextlib
import datetime
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import tempfile
import zipfile


BOOTSTRAP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BOOTSTRAP_DIR)

# Path to "depot_tools"'s "gsutil.py".
GSUTIL_PY = os.path.join(
    os.path.dirname(BASE_DIR), 'depot_tools', 'gsutil.py')

# Base Google Storage bucket name.
SDK_GS_BUCKET_BASE = 'gs://appengine-sdks/featured'

# Extracts the version from a given filename.
VERSION_RE = re.compile(r'^.*[-_](\d+)\.(\d+)\.(\d+)\.zip$')


def parse_yaml(content):
  """Parses deps.lock YAML file content and returns it as python dict."""
  # YAML lib is in venv, not activated here. Do some ugly hacks, they at least
  # don't touch python module import madness. Importing a package from another
  # venv directly into the process space is non-trivial and dangerous.
  oneliner = (
      'import json, sys, yaml; '
      'out = yaml.safe_load(sys.stdin); '
      'json.dump(out, sys.stdout)')
  if sys.platform == 'win32':
    python_venv_path = ('Scripts', 'python.exe')
  else:
    python_venv_path = ('bin', 'python')
  executable = os.path.join(BASE_DIR, 'ENV', *python_venv_path)
  env = os.environ.copy()
  env.pop('PYTHONPATH', None)
  proc = subprocess.Popen(
      [executable, '-c', oneliner],
      executable=executable,
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      env=env)
  return json.loads(proc.communicate(content)[0])


def gsutil(*cmd):
  command = [sys.executable, GSUTIL_PY] + list(cmd)
  logging.debug('Running gsutil command: %s', ' '.join(command))
  return subprocess.check_output(command)


def get_gae_sdk_version(gae_path):
  """Returns the installed GAE SDK version or None."""
  version_path = os.path.join(gae_path, 'VERSION')
  if os.path.isfile(version_path):
    values = dict(
        map(lambda x: x.strip(), l.split(':'))
        for l in open(version_path) if ':' in l)
    if 'release' in values:
      return values['release'].strip('"')


def get_sdk_zip_basename(for_golang):
  """Returns the base name (without version number) of the GAE SDK zip filename.
  """
  if for_golang:
    if sys.platform == 'darwin':
      return 'go_appengine_sdk_darwin_amd64-'
    # Add other platforms as needed.
    return 'go_appengine_sdk_linux_amd64-'
  return 'google_appengine_'


def get_sdk_dirname(for_golang):
  """Returns the expected directory name for the directory of GAE SDK."""
  if for_golang:
    return 'go_appengine'
  return 'google_appengine'


def get_sdk_gs_path(for_golang, version):
  """Returns the expected Google Storage URL to download the GAE SDK."""
  return '%s/%s%s.zip' % (
      SDK_GS_BUCKET_BASE, get_sdk_zip_basename(for_golang), version)


def read_gae_sdk_version_file():
  version_yaml = gsutil('cat', SDK_GS_BUCKET_BASE + '/VERSION')
  version = parse_yaml(version_yaml)
  return version.get('release')


def confirm_sdk_for_version_is_usable(for_golang, version):
  sdk_path = get_sdk_gs_path(for_golang, version)
  try:
    # Read the first byte of the file. This confirms that the file both exists
    # and is readable by this user.
    gsutil('cat', '-r', '-1', sdk_path)
    return True
  except subprocess.CalledProcessError:
    return False


def get_latest_gae_sdk_version(for_golang):
  """Returns the latest GAE SDK and its version."""
  # Attempt to load the VERSION YAML. If we see a version there, confirm that
  # the file for that version is usable.
  try:
    version = read_gae_sdk_version_file()
    if confirm_sdk_for_version_is_usable(for_golang, version):
      return version
  except Exception:
    logging.exception('Failed to get VERSION; scanning...')

  # VERSION failed. Scan the directory and cherry-pick the latest version.
  base_name = get_sdk_zip_basename(for_golang)
  glob_path = '%s/%s*' % (SDK_GS_BUCKET_BASE, base_name)
  contents = gsutil('ls', glob_path).splitlines()
  versions = [
      (m.group(1), m.group(2), m.group(3)) for m in [
          VERSION_RE.match(v)
          for v in contents]
      if m is not None]
  if not versions:
    raise Exception('No versions for [%s] could be identified.' % (base_name,))
  versions.sort(reverse=True)
  return '.'.join(versions[0])


def extract_zip(z, root_path):
  """Extracts files in a zipfile but keep the executable bits."""
  count = 0
  for f in z.infolist():
    perm = (f.external_attr >> 16L) & 0777
    mtime = time.mktime(datetime.datetime(*f.date_time).timetuple())
    filepath = os.path.join(root_path, f.filename)
    logging.debug('Extracting %s', f.filename)
    if f.filename.endswith('/'):
      os.mkdir(filepath, perm)
    else:
      z.extract(f, root_path)
      os.chmod(filepath, perm)
      count += 1
    os.utime(filepath, (mtime, mtime))
  print('Extracted %d files' % count)


@contextlib.contextmanager
def tempdir():
  path = None
  try:
    path = tempfile.mkdtemp(suffix='infra_get_appengine')
    yield path
  finally:
    if path:
      shutil.rmtree(path)


def install_gae_sdk(root_path, for_golang, dry_run, new_version):
  # The zip file already contains 'google_appengine' (for python) or
  # 'go_appengine' (for go) in its path so it's a bit
  # awkward to unzip otherwise. Hard code the path in for now.
  gae_path = os.path.join(root_path, get_sdk_dirname(for_golang))
  print('Looking up path %s' % gae_path)
  version = get_gae_sdk_version(gae_path)
  if version:
    print('Found installed version %s' % version)
    if version == new_version:
      return 0
  else:
    print('Didn\'t find an SDK')

  gs_path = get_sdk_gs_path(for_golang, new_version)
  print('Fetching %s' % gs_path)
  if not dry_run:
    with tempdir() as tdir:
      tmpname = os.path.join(tdir, 'appengine_sdk.zip')
      gsutil('cp', gs_path, tmpname)

      print('Extracting into %s' % gae_path)
      if os.path.isdir(gae_path):
        print('Removing previous version')
        if not dry_run:
          shutil.rmtree(gae_path)

      # Assuming we're extracting there. In fact, we have no idea.
      with zipfile.ZipFile(tmpname, 'r') as z:
        extract_zip(z, root_path)

  return 0


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

  if not options.version:
    options.version = get_latest_gae_sdk_version(options.go)
    if not options.version:
      print >> sys.stderr, 'Failed to find GAE SDK version from download page.'
      return 1
    print('New GAE SDK version is %s' % options.version)

  return install_gae_sdk(
      os.path.abspath(options.dest), options.go, options.dry_run,
      options.version)


if __name__ == '__main__':
  logging.basicConfig(level=logging.ERROR)
  sys.exit(main())
