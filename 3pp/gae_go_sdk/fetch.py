#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import sys

from pkg_resources import parse_version

import requests


def _gae_platform():
  osname, arch = os.environ['_3PP_PLATFORM'].split('-')
  osname = {'mac': 'darwin'}.get(osname, osname)
  return '%s_%s' % (osname, arch)


# SDKs are like `go_appengine_sdk_darwin_386-1.9.77.zip`
ZIP_PREFIX = 'go_appengine_sdk_' + _gae_platform() + '-'


def do_latest():
  BASE_URL = 'https://www.googleapis.com/storage/v1/b/appengine-sdks/o/'
  url = BASE_URL+'?prefix=featured/%s&delimiter=/' % ZIP_PREFIX
  print >>sys.stderr, "Hitting %r" % url
  r = requests.get(url)
  r.raise_for_status()
  data = r.json()
  max_ver, max_string = parse_version(''), ''
  for obj in data['items']:
    ver_string = obj['name'].split('/')[-1].lstrip(ZIP_PREFIX).rstrip('.zip')
    ver = parse_version(ver_string)
    if ver > max_ver:
      max_ver = ver
      max_string = ver_string

  if not max_string:
    print "GOT DATA"
    for obj in data['items']:
      print obj
    raise Exception('failed to find a version')

  print max_string


def do_checkout(version, checkout_path):
  URL = (
    'https://www.googleapis.com/download/storage/v1/b/appengine-sdks/'
    'o/featured%%2F%s%s.zip?alt=media' % (ZIP_PREFIX, version)
  )
  print >>sys.stderr, "fetching", URL
  r = requests.get(URL, stream=True)
  r.raise_for_status()
  outfile = 'archive.zip'
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
      os.environ['_3PP_VERSION'], opts.checkout_path))

  opts = ap.parse_args()
  return opts.func(opts)


if __name__ == '__main__':
  sys.exit(main())
