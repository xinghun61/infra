#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is script to upload ninja_log from googler."""

import argparse
import cStringIO
import gzip
import sys

import httplib2

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server',
                        default='chromium-build-stats.appspot.com',
                        help='server to upload ninjalog file.')
    parser.add_argument('--ninjalog', required=True,
                        help='ninjalog file to upload.')
    args = parser.parse_args()

    output = cStringIO.StringIO()

    with open(args.ninjalog) as f:
        with gzip.GzipFile(fileobj=output, mode='wb') as g:
            g.write(f.read())

    h = httplib2.Http()
    h.request('https://'+args.server+'/upload_ninja_log/', 'POST',
              body=output.getvalue(),
              headers={'Content-Encoding': 'gzip'})

    return 0

if __name__ == '__main__':
    sys.exit(main())
