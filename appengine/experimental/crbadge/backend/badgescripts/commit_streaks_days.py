# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Calculates the longest consecutive days of commits for each person."""

from collections import defaultdict
from datetime import datetime
import json
import os
import sys


_THIRD_PARTY_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                os.path.pardir, os.path.pardir, 'third_party')
sys.path.insert(0, _THIRD_PARTY_DIR)

from local_libs.git_checkout.local_git_repository import LocalGitRepository


_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'


class Streak(object):
  def __init__(self):
    self.days = 0
    self.end_date = None
    self.longest_days = 0

  def ToDict(self):
    return {
      'days': self.days,
      'end_date': self.end_date.strftime(_TIME_FORMAT),
      'longest_days': self.longest_days
    }

  @classmethod
  def FromDict(cls, data):
    instance = cls()
    for key, value in data.iteritems():
      if key == 'end_date':
        value = datetime.strptime(value, _TIME_FORMAT)
      setattr(instance, key, value)
    return instance


def _StreakToDict(results):
  new_dict = {}
  for key, result in results.iteritems():
    new_dict[key] = result.ToDict()
  return new_dict


def _GetStreaks(existing_data, commits):
  results = defaultdict(Streak, existing_data)
  for i in xrange(len(commits)-1, -1, -1):
    commit = commits[i]
    author = commit.author.email
    if (not results[author].end_date or
        (commit.author.time.date() - results[author].end_date.date()).days > 1):
      results[author].end_date = commit.author.time
      results[author].days = 1
    elif (commit.author.time.date() - results[author].end_date.date()).days < 1:
      # Same day change, update end_date.
      results[author].end_date = commit.author.time
    else:
      # Consecutive.
      results[author].end_date = commit.author.time
      results[author].days += 1

    if results[author].longest_days < results[author].days:
      results[author].longest_days = results[author].days

  with open('tmp/streaks', 'w') as outf:
    outf.write(json.dumps(_StreakToDict(results), indent=2))

  return results


def _GetExistingData():
  data = {}
  if not os.path.isfile('tmp/streaks'):
    return data

  with open('tmp/streaks') as inf:
    data = json.loads(inf.read())

    existing_data = {}
    for name, streak in data.iteritems():
      existing_data[name] = Streak.FromDict(streak)

    return existing_data


def _GetStartRevision():
  if not os.path.isfile('tmp/end_revision'):
    return None
  with open('tmp/end_revision') as inf:
    return inf.read()


def _GenerateResults(results):
  data = []
  for email, result in results.iteritems():
    if result.longest_days < 2:
      continue
    data.append({
      'email': email,
      'value': result.longest_days
    })

  return [{
    'badge_name': 'code-number_of_consecutive_days',
    'data': data
  }]


def _SaveLastCheckedRevision(git_repo, end_revision):
  if end_revision == 'HEAD':
    change_log = git_repo.GetChangeLog(end_revision)
    end_revision = change_log.revision

  with open('tmp/end_revision', 'w') as outf:
    outf.write(end_revision)

if __name__ == '__main__':
  git_repo = LocalGitRepository(
      'https://chromium.googlesource.com/chromium/src.git')

  existing_data = _GetExistingData()

  start_revision = (
      _GetStartRevision() or 'a5068f5fa11005232bc4383c54f6af230f9392fb')
  end_revision = 'HEAD'

  commits = git_repo.GetChangeLogs(start_revision, end_revision)
  streaks = _GetStreaks(existing_data, commits)


  _SaveLastCheckedRevision(git_repo, end_revision)
  print json.dumps(_GenerateResults(streaks), indent=4)




