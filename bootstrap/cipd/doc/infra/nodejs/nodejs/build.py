#!/usr/bin/env python2.7
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a simple standalone Python script to construct a CIPD package for
Node.js.

It expects CIPD to be in the path, and uses constants to determine which
sources to use to build the CIPD packages.
"""

import argparse
import collections
import contextlib
import hashlib
import logging
import os
import shutil
import StringIO
import subprocess
import sys
import tarfile
import tempfile
import urllib2


# The common application logger.
LOGGER = logging.getLogger('cipd-nodejs-build')

# Base package name. Platform names will be appended to this for each platform.
CIPD_PACKAGE_BASE = 'infra/nodejs/nodejs'

NodePackage = collections.namedtuple('NodePackage', ('url', 'sha256'))

# The Node.js version.
NODE_VERSION = '4.5.0'

# A map of platform to (URL, SHA256) for each supported package.
PLATFORMS = collections.OrderedDict({
  'linux-amd64': NodePackage(
      url='https://nodejs.org/dist/v4.5.0/node-v4.5.0-linux-x64.tar.gz',
      sha256='5678ad94ee35e40fc3a2c545e136a0dc946ac4c039fca5898e1ea51ecf9e7c39',
  ),
  'mac-amd64': NodePackage(
      url='https://nodejs.org/dist/v4.5.0/node-v4.5.0-darwin-x64.tar.gz',
      sha256='d171f0c859e3895b2430c317001b817866c4de45211ad540c59658ee6a2f689f',
  ),
})


@contextlib.contextmanager
def tempdir():
  tdir = tempfile.mkdtemp(prefix='tmpCIPDNode', dir=os.getcwd())
  try:
    yield tdir
  finally:
    shutil.rmtree(tdir)


def _upload_cipd_package_from(name, root):
  cmd = [
      'cipd', 'create',
      '-name', name,
      '-in', root,
      '-install-mode', 'copy',
      '-ref', 'latest',
      '-tag', 'node_version:%s' % (NODE_VERSION,),
  ]
  LOGGER.debug('Running command: %s', cmd)
  subprocess.check_call(cmd)


def _strip_suffix(v, s):
  if v.endswith(s):
    v = v[:-len(s)]
  return v


def _build_cipd_package(pkg_name, package):
  LOGGER.info('Downloading package for [%s] from: %s', pkg_name, package.url)
  conn = urllib2.urlopen(package.url)
  try:
    data = conn.read()
  finally:
    conn.close()

  # Compare hashes.
  h = hashlib.sha256(data)
  if h.digest() != package.sha256.decode('hex'):
    LOGGER.error('SHA256 of package [%s] (%s) does not match expected (%s)',
        package.url, h.hexdigest(), package.sha256)
    raise ValueError('SHA256 mismatch')

  basedir = _strip_suffix(package.url.split('/')[-1], '.tar.gz')

  # Unpack the file.
  sio = StringIO.StringIO(data)
  tf = tarfile.open(fileobj=sio, mode='r:gz')
  try:
    # Our 'basedir' must be a member.
    if not tf.getmember(basedir):
      LOGGER.error('Package TAR does not include basedir (%s)', basedir)
      raise ValueError('Unexpected TAR contents')

    # Extracted whitelisted files into a temporary directory, and ship that off
    # to CIPD.
    with tempdir() as tdir:
      basedir_whitelist = ['%s/%s/' % (basedir, dname)
                           for dname in ('bin', 'lib', 'include', 'share')]
      for member in tf.getmembers():
        for w in basedir_whitelist:
          if member.name.startswith(w):
            break
        else:
          # Not whitelisted.
          continue
        tf.extract(member, tdir)

      # Package up our basedir.
      _upload_cipd_package_from(pkg_name, os.path.join(tdir, basedir))
  finally:
    tf.close()


def main():
  for platform, package in PLATFORMS.iteritems():
    package_name = '/'.join((CIPD_PACKAGE_BASE, platform))
    _build_cipd_package(package_name, package)
  return 0


if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  sys.exit(main())
