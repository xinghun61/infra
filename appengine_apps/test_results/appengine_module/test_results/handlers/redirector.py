# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(ojan): Get rid of this one crrev.com supports this directly.

import json
import urllib2


# This is just to make testing easier.
def load_url(url):  # pragma: no cover
  return urllib2.urlopen(url).read()


def commit_position_to_hash(commit_position):
  url = 'https://cr-rev.appspot.com/_ah/api/crrev/v1/redirect/%s' % (
      commit_position)
  return str(json.loads(load_url(url))['git_sha'])


def url_from_commit_positions(start_commit_position, end_commit_position):
  start = commit_position_to_hash(start_commit_position)
  end = commit_position_to_hash(end_commit_position)
  return ('https://chromium.googlesource.com/chromium/src/+log'
      '/%s..%s?pretty=fuller' % (start, end))


def get_googlesource_url(handler, *_args, **_kwargs):  # pragma: no cover
  return url_from_commit_positions(handler.request.get('start'),
      handler.request.get('end'))
