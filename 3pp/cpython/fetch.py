#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import sys

import requests


# This is hardcoded to 2.7.15. It seems unlikely that we'll need to release
# another python2 version. If we do, it's easy enough to update.
VERSION = '2.7.15'


def do_latest():
  print VERSION


def do_checkout(version, platform, checkout_path):
  assert version == VERSION, 'only version %r is supported, got %r' % (
    VERSION, version)
  assert 'amd64' not in platform, 'only the 32bit python2 is supported'
  download_url = 'https://www.python.org/ftp/python/%(v)s/python-%(v)s.msi' % {
    'v': version,
  }
  print >>sys.stderr, 'fetching %r' % (download_url,)
  outfile = 'install.msi'
  with open(os.path.join(checkout_path, outfile), 'wb') as f:
    r = requests.get(download_url, stream=True)
    r.raise_for_status()
    for chunk in r.iter_content(1024**2):
      f.write(chunk)


def main():
  ap = argparse.ArgumentParser()
  sub = ap.add_subparsers()

  latest = sub.add_parser("latest")
  latest.set_defaults(func=lambda _opts: do_latest())

  checkout = sub.add_parser("checkout")
  checkout.add_argument("checkout_path")
  checkout.set_defaults(
    func=lambda opts: do_checkout(
      os.environ['_3PP_VERSION'], os.environ['_3PP_PLATFORM'],
      opts.checkout_path))

  opts = ap.parse_args()
  return opts.func(opts)


if __name__ == '__main__':
  sys.exit(main())
