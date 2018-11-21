#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is script to upload ninja_log from googler."""

import argparse
import cStringIO
import gzip
import json
import logging
import multiprocessing
import os
import platform
import socket
import sys

import httplib2

def IsGoogler(server):
    """Check whether this script run inside corp network."""
    h = httplib2.Http()
    _, content = h.request('https://'+server+'/should-upload', 'GET')
    return content == 'Success'

def GetMetadata(args):
    """Get metadata for uploaded ninjalog."""

    # TODO(tikuta): Support build_configs from args.gn.

    build_dir = os.path.dirname(args.ninjalog)
    metadata = {
        'platform': platform.system(),
        'cwd': build_dir,
        'hostname': socket.gethostname(),
        'cpu_core': multiprocessing.cpu_count(),
        'cmdline': args.cmdline,
    }

    return metadata

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server',
                        default='chromium-build-stats.appspot.com',
                        help='server to upload ninjalog file.')
    parser.add_argument('--ninjalog', required=True,
                        help='ninjalog file to upload.')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose logging.')
    parser.add_argument('--cmdline', nargs=argparse.REMAINDER,
                        help='command line args passed to ninja.')

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        # Disable logging.
        logging.disable(logging.CRITICAL)

    if not IsGoogler(args.server):
        return 0

    output = cStringIO.StringIO()

    with open(args.ninjalog) as f:
        with gzip.GzipFile(fileobj=output, mode='wb') as g:
            g.write(f.read())
            g.write('# end of ninja log\n')

            metadata = GetMetadata(args)
            logging.info('send metadata: %s', metadata)
            g.write(json.dumps(metadata))

    h = httplib2.Http()
    resp_headers, content = h.request(
        'https://'+args.server+'/upload_ninja_log/', 'POST',
        body=output.getvalue(), headers={'Content-Encoding': 'gzip'})

    if resp_headers.status != 200:
        logging.warn("unexpected status code for response: %s",
                     resp_headers.status)
        return 1

    logging.info('response header: %s', resp_headers)
    logging.info('response content: %s', content)
    return 0

if __name__ == '__main__':
    sys.exit(main())
