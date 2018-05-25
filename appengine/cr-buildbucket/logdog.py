# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides utility functions for interacting with LogDog streams."""


import urlparse


def parse_url(url):
  # LogDog URL example:
  #   'logdog://logs.chromium.org/chromium/'
  #   'buildbucket/cr-buildbucket.appspot.com/8953190917205316816/+/annotations'
  u = urlparse.urlparse(url)
  full_path = u.path.strip('/').split('/')
  if (u.scheme != 'logdog' or u.params or u.query or u.fragment or
      len(full_path) < 4 or '+' not in full_path):
    raise ValueError('invalid logdog URL %r' % url)
  project = full_path[0]
  plus_pos = full_path.index('+')
  stream_prefix = '/'.join(full_path[1:plus_pos])
  stream_name = '/'.join(full_path[plus_pos + 1:])
  return u.netloc, project, stream_prefix, stream_name
