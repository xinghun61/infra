# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
from collections import defaultdict
from collections import namedtuple
import json
import os
import re
import threading

from local_libs import script_util
from local_libs.git_checkout.local_git_repository import LocalGitRepository

_TBR_REGEX = re.compile(r'TBR=(.*)')

_CHROMIUM_SRC = 'https://chromium.googlesource.com/chromium/src'

_BADGE_TO_REPO_URL = {
    'code-landed_in_chromium_browser':
        'https://chromium.googlesource.com/chromium/src',
    'code-landed_in_angle':
        'https://chromium.googlesource.com/angle/angle',
    'code-landed_in_arc':
        'https://chromium.googlesource.com/arc',
    'code-landed_in_breakpad':
        'https://chromium.googlesource.com/breakpad/breakpad',
    'code-landed_in_catapult':
        'https://chromium.googlesource.com/catapult',
    'code-landed_in_crashpad':
        'https://chromium.googlesource.com/crashpad',
    'code-landed_in_infra':
        'https://chromium.googlesource.com/infra',
    'code-landed_in_libyuv':
        'https://chromium.googlesource.com/libyuv/libyuv',
    'code-landed_in_media_router':
        'https://chromium.googlesource.com/media_router',
    'code-landed_in_native_client':
        'https://chromium.googlesource.com/native_client',
    'code-landed_in_skia':
        'https://chromium.googlesource.com/skia',
    'code-landed_in_v8':
        'https://chromium.googlesource.com/v8/v8',
    'code-landed_in_webm':
        'https://chromium.googlesource.com/webm',
}

_BADGES = [
    'code-landed_in_chromium_browser',
    #'code-landed_in_angle',
    #'code-landed_in_arc',
    #'code-landed_in_breakpad',
    #'code-landed_in_catapult',
    #'code-landed_in_crashpad',
    'code-landed_in_infra',
    #'code-landed_in_libyuv',
    #'code-landed_in_media_router',
    #'code-landed_in_native_client',
    'code-landed_in_skia',
    'code-landed_in_v8',
    #'code-landed_in_webm',
    'code-number_of_tbrs',
    'code-number_of_tbrs_assigned',
]

_STATE_STORAGE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   '.state')
if not os.path.exists(_STATE_STORAGE_PATH):
  os.makedirs(_STATE_STORAGE_PATH)


def GetFunctionAndRepoUrlForBadge(badge):
  repo_url = _BADGE_TO_REPO_URL.get(badge, _CHROMIUM_SRC)
  if badge.startswith('code-landed_in'):
    return CommitLandedInRepo, repo_url

  if badge == 'code-number_of_tbrs':
    return NumberOfTBR, repo_url

  if badge == 'code-number_of_tbrs_assigned':
    return NumberOfTBRAsigned, repo_url


def CommitLandedInRepo(changelogs, author_data, lock):
  for changelog in changelogs:
    with lock:
      author_data[changelog.author.email] += 1


def NumberOfTBR(changelogs, author_data, lock):
  """Returns the number of TBR authors in a list of commits."""
  for changelog in changelogs:
    match = _TBR_REGEX.search(changelog.message)
    if match:
      with lock:
        author_data[changelog.author.email] += 1


def NumberOfTBRAsigned(changelogs, author_data, lock):
  """Returns the number TBR assigned authors in a list of commits."""
  for changelog in changelogs:
    match = _TBR_REGEX.search(changelog.message)
    if match:
      tbr_assigneds = match.group(1).split(',')
      with lock:
        for tbr_assigned in tbr_assigneds:
          author_data[tbr_assigned] += 1


class State(object):

  def __init__(self, revision, author_data):
    self.revision = revision
    self.author_data = author_data


def GetAuthorDataInRepo(func, state, repo_url=None, n=20):
  """Run func to update author_data based on current revision, author_data."""
  repo_url = repo_url or _CHROMIUM_SRC
  lock = threading.Lock()
  commits_landed_in_repo = defaultdict(int)
  repository = LocalGitRepository(repo_url)
  # Get all the changelogs from the beginning.
  changelogs = repository.GetChangeLogs(state.revision, None)

  if not changelogs:
    return

  tasks = []
  number_of_cls = len(changelogs)
  if number_of_cls > n:
    segments = []
    for index in xrange(0,  number_of_cls, n):
      segments.append(changelogs[index: (index + n)])
  else:
    segments = [changelogs]

  for segment in segments:
    tasks.append({'function': func,
                  'args': [segment, state.author_data, lock]})

  # Update state.author_data based on information from state.revision to the
  # latest commit.
  script_util.RunTasks(tasks)

  # Update the state.revision to the current end_revision to keep track of the
  # state of this run.
  state.revision = changelogs[0].revision


def ProcessAuthorDataToUploadFormat(author_data):
  return [{'email': email, 'value': value}
          for email, value in author_data.iteritems()]


def LoadStateFromLastRun(badge):
  path = os.path.join(_STATE_STORAGE_PATH, badge)
  if not os.path.exists(path):
    return State(None, defaultdict(int))

  with open(path) as f:
    state_info = json.load(f)

  return State(state_info['revision'], state_info['author_data'])


def FlushCurrentState(badge, state):
  with open(os.path.join(_STATE_STORAGE_PATH, badge), 'wb') as f:
    state_info = json.dump({
        'revision': state.revision,
        'author_data': state.author_data,
    }, f)


def ComputeCommitBadge(badge):
  """Compute commit type of badges."""
  func, repo_url = GetFunctionAndRepoUrlForBadge(badge)
  state = LoadStateFromLastRun(badge)
  # The state is updated to the latest.
  GetAuthorDataInRepo(func, state, repo_url=repo_url)
  badge_info = {'badge_name': badge,
                'data': ProcessAuthorDataToUploadFormat(state.author_data)}
  FlushCurrentState(badge, state)
  return badge_info


if __name__ == '__main__':
  badge_infos = [ComputeCommitBadge(badge) for badge in _BADGES]
  print json.dumps(badge_infos, indent=2, sort_keys=True)
