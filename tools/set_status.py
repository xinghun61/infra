#!/usr/bin/env python
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import getpass
import sys
import urllib


if len(sys.argv) != 4:
  print('Usage: set_status.py url username message')
  sys.exit(1)

def post(url, username, message):
  if not url.startswith('https://'):
    url = 'https://' + url
  data = {
      'message': message,
      'username': username,
      'password': getpass.getpass(),
  }
  print url
  out = urllib.urlopen(url + '/status', urllib.urlencode(data)).read()
  print out

post(*sys.argv[1:])
