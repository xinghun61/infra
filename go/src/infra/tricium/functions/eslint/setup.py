#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess
import urllib2
import tarfile

NODE_VERSION = '8.12.0'
ESLINT_VERSION = '5.8.0'

def main():
    node_url = 'https://nodejs.org/dist/v8.12.0/node-v{0}-linux-x64.tar.gz' \
        .format(NODE_VERSION)
    eslint_url = 'https://github.com/eslint/eslint/archive/v{0}.tar.gz' \
        .format(ESLINT_VERSION)

    download_urls = [node_url, eslint_url]
    file_names = ['node.tar.gz', 'eslint.tar.gz']

    for url, fname in zip(download_urls, file_names):
        if not os.path.isfile(fname):
            with open(fname, 'wb') as f:
                r = urllib2.urlopen(url)
                content = r.read()
                f.write(content)

    for fname in file_names:
        try:
            tar = tarfile.open(fname, 'r:gz')
            tar.extractall()
            tar.close()
        except tarfile.ReadError:
            print('Error trying to read {0}'.format(fname))

    if not os.path.isdir('node'):
        os.rename('node-v{0}-linux-x64'.format(NODE_VERSION), 'node')
    if not os.path.isdir('eslint'):
        os.rename('eslint-{0}'.format(ESLINT_VERSION), 'eslint')

    os.chdir('eslint')
    try:
        subprocess.check_call([
            '../node/bin/node',
            '../node/lib/node_modules/npm/bin/npm-cli.js',
            'install'
        ])
    except subprocess.CalledProcessError:
        print('Failed in installing eslint dependencies')
    except OSError:
        print('Wrong binary format for the current architecture')

if __name__ == '__main__':
    main()
