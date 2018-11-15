#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import re
import sys

import requests


# A regex for a name of the release asset to package, available at
# https://github.com/activescott/lessmsi
WINDOWS_ASSET_RE = re.compile(r'^lessmsi-v.*\.zip$')


def do_latest():
  r = requests.get(
    'https://api.github.com/repos/activescott/lessmsi/releases/latest')
  r.raise_for_status()
  print r.json()['tag_name'].lstrip('v')


def do_checkout(version, checkout_path):
  r = requests.get(
    'https://api.github.com/repos/activescott/lessmsi/releases')
  r.raise_for_status()

  download_url = None
  asset_name = None

  target_tag = 'v%s' % (version,)
  for release in r.json():
    if str(release['tag_name']) == target_tag:
      for asset in release['assets']:
        asset_name = str(asset['name'])
        if WINDOWS_ASSET_RE.match(asset_name):
          download_url = asset['browser_download_url']
          break
      break
  if not download_url:
    raise Exception('could not find download_url')

  print >>sys.stderr, "fetching", download_url
  r = requests.get(download_url, stream=True)
  r.raise_for_status()
  with open(os.path.join(checkout_path, asset_name), 'wb') as f:
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
      os.environ['_3PP_VERSION'], opts.checkout_path))

  opts = ap.parse_args()
  return opts.func(opts)


if __name__ == '__main__':
  sys.exit(main())
