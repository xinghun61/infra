#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import sys

import requests

from pkg_resources import parse_version

BASE_URL = 'https://nodejs.org/dist/'

def do_latest():
  data = requests.get(BASE_URL + 'index.json').json()
  max_version, max_string = parse_version('0'), '0'
  for release in data:
    s = release['version'].lstrip('v')
    v = parse_version(s)
    if v > max_version:
      max_version = v
      max_string = s

  print str(max_string)


def do_checkout(version, platform, checkout_path):
  targ_os, targ_arch = platform.split('-')
  ext = 'zip' if targ_os == 'windows' else 'tar.gz'
  fragment = {
    ('mac', 'amd64'): 'darwin-x64',

    ('linux', 'amd64'): 'linux-x64',

    ('linux', 'armv6l'): 'linux-armv6l',
    ('linux', 'arm64'): 'linux-arm64',

    ('windows', 'amd64'): 'win-x64',
  }[(targ_os, targ_arch)]
  download_url = (
    '%(base)s/v%(version)s/node-v%(version)s-%(fragment)s.%(ext)s'
    % {
      'base': BASE_URL,
      'version': version,
      'fragment': fragment,
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
