#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import re
import subprocess
import sys

from pkg_resources import parse_version

import requests


def do_latest():
  """This is pretty janky, but the apache generic Index page hasn't changed
  since forever. It contains links (a tags with href's) to the different
  version folders."""
  r = requests.get('https://www.python.org/ftp/python/')
  r.raise_for_status()
  highest = None
  href_re = re.compile(r'href="(\d+\.\d+\.\d+)/"')
  for m in href_re.finditer(r.text):
    v = parse_version(m.group(1))
    if not highest or v > highest:
      highest = v
  print highest


def do_checkout(version, platform, checkout_path):
  assert '386' not in platform, 'only the 32bit python2 is supported'
  download_url = (
    'https://www.python.org/ftp/python/%(v)s/python-%(v)s-amd64-webinstall.exe'
    % {'v': version}
  )
  print >>sys.stderr, 'fetching %r' % (download_url,)
  outfile = 'install.exe'
  with open(os.path.join(checkout_path, outfile), 'wb') as f:
    r = requests.get(download_url, stream=True)
    r.raise_for_status()
    for chunk in r.iter_content(1024**2):
      f.write(chunk)

  # downloads all the *.msi files locally.
  subprocess.check_call([
    os.path.join(checkout_path, outfile), '/layout', checkout_path, '/quiet'])


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
