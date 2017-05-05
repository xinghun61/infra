#!/usr/bin/env python3
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
import io
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request


# The common application logger.
LOGGER = logging.getLogger('cipd-nodejs-build')

# Base package name. Platform names will be appended to this for each platform.
CIPD_PACKAGE_BASE = 'infra/nodejs/nodejs'

NodeParams = collections.namedtuple('NodeParams', ('version',))
NodePackage = collections.namedtuple('NodePackage', ('filename', 'sha256'))

# Node parameter dictionary.
NODE_PARAMS = NodeParams(
    # The Node.js version.
    version='6.10.3',
)

# URL template for a Node.js package.
NODE_URL_TEMPLATE = 'https://nodejs.org/dist/v%(version)s/%(filename)s'

# A map of platform to (URL, SHA256) for each supported package.
PLATFORMS = collections.OrderedDict({
  'linux-amd64': NodePackage(
      filename = 'node-v%(version)s-linux-x64.tar.xz',
      sha256='00d0aea8e47a68da6e3278d7c2fc1504de46a34d97b4b2fa5610b04a64fce04c',
  ),
  'mac-amd64': NodePackage(
      filename = 'node-v%(version)s-darwin-x64.tar.gz',
      sha256='c09b2e60b7c12d88199d773f7ce046a6890e7c5d3be0cf68312ae3da474f32a2',
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
      '-tag', 'node_version:%s' % (NODE_PARAMS.version,),
  ]
  LOGGER.debug('Running command: %s', cmd)
  subprocess.check_call(cmd)


def _strip_extension(v):
  for ext in ('.tar.gz', '.tar.xz'):
    if v.endswith(ext):
      return v[:-len(ext)]
  return v


def _build_cipd_package(pkg_name, package):
  params = NODE_PARAMS._asdict()
  params.update({
    'filename': package.filename % params,
  })
  url = NODE_URL_TEMPLATE % params

  LOGGER.info('Downloading package for [%s] from: %s', pkg_name, url)
  with urllib.request.urlopen(url) as conn:
    data = conn.read()

  # Compare hashes.
  h = hashlib.sha256(data)
  if h.hexdigest().lower() != package.sha256.lower():
    LOGGER.error('SHA256 of package [%s] (%s) does not match expected (%s)',
        url, h.hexdigest(), package.sha256)
    raise ValueError('SHA256 mismatch')

  basedir = _strip_extension(url.split('/')[-1])

  # Unpack the file.
  bio = io.BytesIO(data)
  tf = tarfile.open(fileobj=bio, mode='r:*')
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
  for platform, package in PLATFORMS.items():
    package_name = '/'.join((CIPD_PACKAGE_BASE, platform))
    _build_cipd_package(package_name, package)
  return 0


if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  sys.exit(main())
