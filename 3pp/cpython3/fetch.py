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


def get_webinstaller_suffix(platform):
  if platform == 'windows-386':
    return '-webinstall.exe'
  if platform == 'windows-amd64':
    return '-amd64-webinstall.exe'
  raise ValueError('fetch.py is only supported for windows-386, windows-amd64')


def do_latest(platform):
  """This is pretty janky, but the apache generic Index page hasn't changed
  since forever. It contains links (a tags with href's) to the different
  version folders."""
  suf = get_webinstaller_suffix(platform)
  # Find the highest version e.g. 3.8.0.
  r = requests.get('https://www.python.org/ftp/python/')
  r.raise_for_status()
  highest = None
  href_re = re.compile(r'href="(\d+\.\d+\.\d+)/"')
  for m in href_re.finditer(r.text):
    v = parse_version(m.group(1))
    if not highest or v > highest:
      highest = v
  r = requests.get('https://www.python.org/ftp/python/%s/' % highest)
  r.raise_for_status()
  # Find the highest release e.g. 3.8.0a4.
  highest = None
  href_re = re.compile(r'href="python-(\d+\.\d+\.\d+((a|b|rc)\d+)?)%s"' % suf)
  for m in href_re.finditer(r.text):
    v = parse_version(m.group(1))
    if not highest or v > highest:
      highest = v
  print highest


def do_checkout(version, platform, checkout_path):
  # e.g. 3.8.0a4 -> 3.8.0
  short = version
  short_re = re.compile(r'(\d+\.\d+\.\d+)')
  m = short_re.match(version)
  if m:
    short = m.group(0)
  download_url = (
    'https://www.python.org/ftp/python/%(short)s/python-%(ver)s%(suf)s'
    % {'short': short, 'ver': version, 'suf': get_webinstaller_suffix(platform)}
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
  latest.set_defaults(func=lambda _opts: do_latest(os.environ['_3PP_PLATFORM']))

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
