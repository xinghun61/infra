#!/usr/bin/env python
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import urllib

from set_lkgr import get_pwd


def post(username, message, url='chromium-status.appspot.com'):
  if not url.startswith('https://'):
    url = 'https://' + url
  data = {
      'message': message,
      'username': username,
      'password': get_pwd(),
  }
  print url
  out = urllib.urlopen(url + '/status', urllib.urlencode(data)).read()
  print out
  return 0


if __name__ == '__main__':
  if not (3 <= len(sys.argv) <= 4):
    print('Usage: set_status.py username message [url]')
    sys.exit(1)

  sys.exit(post(*sys.argv[1:]))
