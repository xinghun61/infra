#!/usr/bin/env python
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import optparse
import os
import sys
import urllib


def post(url, data):
  return urllib.urlopen(url, urllib.urlencode(data)).read()


def main():
  BASE_DIR = os.path.dirname(os.path.abspath(__file__))
  parser = optparse.OptionParser()
  parser.add_option('-v', '--verbose', action='count', default=0)
  options, args = parser.parse_args()

  logging.basicConfig(level=
      [logging.WARNING, logging.INFO, logging.DEBUG][
        min(2, options.verbose)])
  if len(args) != 1:
    parser.error('Url of server')

  url = args[0].rstrip('/')
  total = 0
  for data in json.load(open(os.path.join(BASE_DIR, 'cq.json'))):
    packet = {
        'password': 'foobar',
        'p': json.dumps(data),
    }
    total += int(post(url + '/cq/receiver', packet))
  if total != 6:
    print >> sys.stderr, 'Unexpected length: %d' % total
    return 1
  return 0


if __name__ == '__main__':
  sys.exit(main())
