#!/usr/bin/env python
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import optparse
import os
import sys
import time
import urllib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def post(url, data):
  return urllib.urlopen(url, urllib.urlencode(data)).read()


def load_json():
  data = json.load(open(os.path.join(BASE_DIR, 'cq.json')))
  # Use 31 days ago as the offset.
  offset = 60*60*24*31
  for line in data:
    line['timestamp'] += time.time() - offset
  return data


def load_packets():
  return [
    {
      'password': 'foobar',
      'p': json.dumps(data),
    } for data in load_json()
  ]


def main():
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
  for packet in load_packets():
    output = post(url + '/cq/receiver', packet)
    try:
      total += int(output)
    except ValueError:
      print output
  if total != 7:
    print >> sys.stderr, 'Unexpected length: %d' % total
    return 1
  return 0


if __name__ == '__main__':
  sys.exit(main())
