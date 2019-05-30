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


def get_installer_suffix(platform):
  if platform == 'windows-386':
    return '.msi'
  if platform == 'windows-amd64':
    return '.amd64.msi'
  raise ValueError('fetch.py is only supported for windows-386, windows-amd64')


def do_latest():
  print VERSION


def do_checkout(version, platform, checkout_path):
  if version != VERSION:
    raise ValueError('fetch.py is only supported for cpython %s' % VERSION)
  url = 'https://www.python.org/ftp/python/%(v)s/python-%(v)s%(suf)s' % {
    'v': version, 'suf': get_installer_suffix(platform),
  }
  print >>sys.stderr, 'fetching %r' % (url,)
  outfile = 'install.msi'
  with open(os.path.join(checkout_path, outfile), 'wb') as f:
    r = requests.get(url, stream=True)
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
