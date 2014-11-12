# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Gitiles client for GAE environment."""

from collections import namedtuple
from datetime import datetime, timedelta
import re

# pylint: disable=W0611
from gitiles.googlesource import (GoogleSourceServiceClient, Error,
                                  AuthenticationError)


GitContributor = namedtuple('GitContributor', ['name', 'email', 'time'])
Commit = namedtuple('Commit', ['sha', 'tree', 'parents', 'author', 'committer',
                               'message'])


def parse_time(tm):
  """Converts time in Gitiles-specific format to datetime."""
  tm_parts = tm.split()
  # Time stamps from gitiles sometimes have a UTC offset (e.g., -0800), and
  # sometimes not.  time.strptime() cannot parse UTC offsets, so if one is
  # present, strip it out and parse manually.
  timezone = None
  if len(tm_parts) == 6:
    tm = ' '.join(tm_parts[:-1])
    timezone = tm_parts[-1]
  dt = datetime.strptime(tm, "%a %b %d %H:%M:%S %Y")
  if timezone:
    m = re.match(r'([+-])(\d\d):?(\d\d)?', timezone)
    assert m, 'Could not parse time zone information from "%s"' % timezone
    timezone_delta = timedelta(
        hours=int(m.group(2)), minutes=int(m.group(3) or '0'))
    if m.group(1) == '-':
      dt += timezone_delta
    else:
      dt -= timezone_delta
  return dt


class GitilesClient(GoogleSourceServiceClient):
  """Client class for Gitiles operations."""

  def get_commit(self, project, commit_sha):
    """Gets a single Git commit.

    Returns Commit object, or None if the commit was not found.
    """
    path = '%s/+/%s?format=json' % (project, commit_sha)
    data = self._fetch(path)
    if data is None:
      return None

    def parse_contributor(data):
      if data is None:
        return None
      time = data.get('time')
      if time is not None:
        time = parse_time(time)
      return GitContributor(
          name=data.get('name'),
          email=data.get('email'),
          time=time,
      )

    return Commit(
        sha=data['commit'],
        tree=data.get('tree'),
        parents=data.get('parents'),
        author=parse_contributor(data.get('author')),
        committer=parse_contributor(data.get('committer')),
        message=data.get('message'),
    )
