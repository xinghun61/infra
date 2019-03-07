#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fetches dependencies (node, eslint) for the eslint analyzer."""

import os
import subprocess
import sys
import tarfile
import urllib2

NODE_VERSION = '8.12.0'


def main():
    if not os.path.isdir('node'):
        fetch_node()
    npm_install()
    sys.exit(0)


def fetch_node():
    """Downloads a pinned version of node.js and unpacks it.

    The downloaded Node binary is platform-specific; it's important that the
    platform here matches the platform where the ESLint analyzer is run because
    the Node binary is uploaded and run by the analyzer.
    """
    url = 'https://nodejs.org/dist/v{0}/node-v{0}-linux-x64.tar.gz'.format(
        NODE_VERSION)
    archive_name = 'node.tar.gz'
    with open(archive_name, 'wb') as f:
        content = urllib2.urlopen(url).read()
        f.write(content)

    # Unzip the resulting archive.
    try:
        tar = tarfile.open(archive_name, 'r:gz')
        tar.extractall()
        tar.close()
    except tarfile.ReadError:
        print('Error trying to read {0}.'.format(archive_name))
        sys.exit(1)

    # Rename the directory.
    assert not os.path.isdir('node')
    os.rename('node-v{0}-linux-x64'.format(NODE_VERSION), 'node')


def npm_install():
    """Runs npm install to get eslint and all other dependencies."""
    try:
        subprocess.check_call([
            'node/bin/node',
            'node/lib/node_modules/npm/bin/npm-cli.js',
            'install',
        ])
    except subprocess.CalledProcessError:
        print('Failed in installing eslint dependencies.')
        sys.exit(1)
    except OSError:
        print('Wrong binary format for the current architecture.')
        sys.exit(1)


if __name__ == '__main__':
    main()
