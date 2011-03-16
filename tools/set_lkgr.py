#!/usr/bin/env python
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import getpass
import os
import sys
import urllib


def get_pwd():
  if os.path.isfile('.status_password'):
    return open('.status_password', 'r').read().strip()
  return getpass.getpass()


def post(revision, url='chromium-status.appspot.com'):
  if not url.startswith('https://'):
    url = 'https://' + url
  data = {
      'revision': revision,
      'success': 1,
      'password': get_pwd(),
  }
  print url
  out = urllib.urlopen(url + '/revisions', urllib.urlencode(data)).read()
  print out
  return 0


if __name__ == '__main__':
  if not (2 <= len(sys.argv) <= 3):
    print('Usage: set_lkgr.py revision [url]')
    sys.exit(1)

  sys.exit(post(*sys.argv[1:]))
