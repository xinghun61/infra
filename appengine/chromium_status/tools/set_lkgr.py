#!/usr/bin/env python
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import getpass
import os
import re
import sys
import urllib


def usage():
  print('Usage: set_lkgr.py revision [git_hash [url]]')
  sys.exit(1)


def get_pwd():
  if os.path.isfile('.status_password'):
    return open('.status_password', 'r').read().strip()
  return getpass.getpass()


def post(revision, git_hash='', url='chromium-status.appspot.com'):
  if not re.match('^([a-zA-Z0-9]{40})?$', git_hash):
    print 'Git hash must match /^([a-zA-Z0-9]{40})?$/.'
    usage()
  if not url.startswith('https://') and not url.startswith('http://'):
    url = 'https://' + url
  if url.startswith('http://'):
    print('WARNING: Using set_lkgr.py with an http:// url only works on '
          'the dev_appserver.')
    if raw_input('Continue (y/N): ').lower() != 'y':
      print 'Aborting.'
      sys.exit(1)
  data = {
      'revision': revision,
      'success': 1,
      'git_hash': git_hash,
      'password': get_pwd(),
  }
  print url
  out = urllib.urlopen(url + '/revisions', urllib.urlencode(data)).read()
  print out
  return 0


if __name__ == '__main__':
  if not (2 <= len(sys.argv) <= 4):
    usage()

  sys.exit(post(*sys.argv[1:]))
