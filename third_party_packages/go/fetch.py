#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import sys

import requests


def do_latest():
  print requests.get('https://golang.org/VERSION?m=text').text.replace('go', '')


def do_checkout(version, platform, checkout_path):
  platform = platform.replace('mac', 'darwin')
  ext = 'zip' if platform.startswith('windows') else 'tar.gz'
  download_url = (
    'https://storage.googleapis.com/golang/go%(version)s.%(platform)s.%(ext)s'
    % {
      'version': version,
      'platform': platform,
      'ext': ext
    })
  print >>sys.stderr, "fetching", download_url
  r = requests.get(download_url, stream=True)
  r.raise_for_status()
  outfile = 'archive.'+ext
  with open(os.path.join(checkout_path, outfile), 'wb') as f:
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
