#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fetches dependencies (node, eslint) for the eslint analyzer."""

import os
import subprocess
import urllib2
import tarfile

NODE_VERSION = '8.12.0'


def main():
    # Download a pinned version of node.js.
    url = 'https://nodejs.org/dist/v{0}/node-v{0}-linux-x64.tar.gz'.format(
        NODE_VERSION)
    archive_name = 'node.tar.gz'
    with open(archive_name, 'wb') as f:
        content = urllib2.urlopen(url).read()
        f.write(content)

    # Unzip and rename the resulting directory.
    try:
        tar = tarfile.open(archive_name, 'r:gz')
        tar.extractall()
        tar.close()
    except tarfile.ReadError:
        print('Error trying to read {0}'.format(archive_name))

    if not os.path.isdir('node'):
        os.rename('node-v{0}-linux-x64'.format(NODE_VERSION), 'node')

    # Run npm install to get eslint and all other dependencies.
    try:
        subprocess.check_call([
            'node/bin/node',
            'node/lib/node_modules/npm/bin/npm-cli.js',
            'install',
            'eslint',
            'eslint-config-google',
        ])
    except subprocess.CalledProcessError:
        print('Failed in installing eslint dependencies')
    except OSError:
        print('Wrong binary format for the current architecture')


if __name__ == '__main__':
    main()
