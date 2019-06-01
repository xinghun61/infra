#!/usr/bin/env python
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
import os
import sys

import requests


# https://developer.github.com/v3/repos/releases/#get-the-latest-release
# Returns a JSON-loadable text response like:
# {
#   ...,
#   "assets": [
#     {
#       ...,
#       "browser_download_url": "...",
#       ...,
#       "name": "protoc-3.8.0-win32.zip",
#       ...,
#     },
#     ...
#   ],
#   ...
#   "tag_name": "v3.8.0",
#   ...
# }
#
# Of interest are tag_name, which contains the version, and assets, which
# details platform-specific binaries. Under assets, name indicates the platform
# and browser_download_url indicates where to download a zip file containing the
# prebuilt binary.
LATEST = 'https://api.github.com/repos/protocolbuffers/protobuf/releases/latest'


# A mapping of supported CIPD platforms to the name of the corresponding protoc
# platform.
PROTOC_PLATFORMS = {
    'linux-amd64': 'linux-x86_64',
    'mac-amd64': 'osx-x86_64',
    'windows-386': 'win32',
    'windows-amd64': 'win64',
}


def do_latest():
  r = requests.get(LATEST)
  r.raise_for_status()
  print json.loads(r.text)['tag_name'][1:] # e.g. v3.8.0 -> 3.8.0


def fetch(url, outfile):
  print >>sys.stderr, 'fetching %r' % url
  with open(outfile, 'wb') as f:
    r = requests.get(url, stream=True)
    r.raise_for_status()
    for chunk in r.iter_content(1024**2):
      f.write(chunk)


def do_checkout(version, platform, checkout_path):
  if platform not in PROTOC_PLATFORMS:
    raise ValueError('unsupported platform %s' % platform)
  name = 'protoc-%s-%s.zip' % (version, PROTOC_PLATFORMS[platform])

  r = requests.get(LATEST)
  r.raise_for_status()
  rsp = json.loads(r.text)
  latest = rsp['tag_name'][1:]
  if version != latest:
    # Race between calling latest and checkout.
    raise ValueError('expected %s, latest is %s' % (version, latest))

  for a in rsp['assets']:
    if a['name'] == name:
      fetch(a['browser_download_url'], os.path.join(checkout_path, name))
      return
  raise ValueError('missing release for supported platform %s' % platform)


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
