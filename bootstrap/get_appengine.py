#!/usr/bin/env python
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import optparse
import os
import re
import shutil
import sys
import time
import tempfile
import urllib2
import zipfile


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

URLOPEN_RETRIES = 5

SDK_URL_BASE = 'https://storage.googleapis.com/appengine-sdks/featured/'


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


def get_sdk_url(for_golang, version):
  """Returns the expected URL to download the GAE SDK."""
  return SDK_URL_BASE + get_sdk_zip_basename(for_golang) + version + '.zip'


def get_latest_gae_sdk_version(for_golang):
  """Returns the url to get the latest GAE SDK and its version."""
  url = 'https://cloud.google.com/appengine/downloads.html'
  logging.debug('%s', url)

  for retry in xrange(URLOPEN_RETRIES):
    try:
      content = urllib2.urlopen(url).read()
      break
    except urllib2.HTTPError as e:
      if e.code == 500 and retry < URLOPEN_RETRIES - 1:
        delay = 2 ** retry
        logging.info('Failed to get %s. Retrying after %d seconds.', url, delay)
        time.sleep(delay)
      else:
        raise e

  # Calculate the version from the url.
  re_base = re.escape(SDK_URL_BASE + get_sdk_zip_basename(for_golang))
  m = re.search(re_base + r'([0-9\.]+?)\.zip', content)
  if m:
    return m.group(1)


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

  url = get_sdk_url(for_golang, new_version)
  print('Fetching %s' % url)
  if not dry_run:
    try:
      u = urllib2.urlopen(url)
    except urllib2.HTTPError as exc:
      # If we fail to download the new version, maintain the old one in place.
      # http://crbug.com/593481
      print ('Failed to download sdk: %s' % url)
      print exc
      return 1

    if os.path.isdir(gae_path):
      print('Removing previous version')
      if not dry_run:
        shutil.rmtree(gae_path)

    with tempfile.NamedTemporaryFile() as f:
      while True:
        chunk = u.read(2 ** 20)
        if not chunk:
          break
        f.write(chunk)
      # Assuming we're extracting there. In fact, we have no idea.
      print('Extracting into %s' % gae_path)
      z = zipfile.ZipFile(f, 'r')
      try:
        extract_zip(z, root_path)
      finally:
        z.close()
  return 0


def main():
  parser = optparse.OptionParser(prog='python -m %s' % __package__)
  parser.add_option('-v', '--verbose', action='store_true')
  parser.add_option(
      '-g', '--go', action='store_true', help='Defaults to python SDK')
  parser.add_option(
      '-d', '--dest', default=os.path.dirname(BASE_DIR), help='Output')
  parser.add_option('--version', help='Specify which version to fetch')
  parser.add_option('--dry-run', action='store_true', help='Do not download')
  options, args = parser.parse_args()
  if args:
    parser.error('Unsupported args: %s' % ' '.join(args))
  logging.basicConfig(level=logging.DEBUG if options.verbose else logging.ERROR)

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
  sys.exit(main())
