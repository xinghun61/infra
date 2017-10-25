# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
from collections import defaultdict
import json
import re
import threading

from local_libs import script_util
from local_libs.git_checkout.local_git_repository import LocalGitRepository

_TBR_REGEX = re.compile(r'TBR=(.*)')

_CHROMIUM_SRC = 'https://chromium.googlesource.com/chromium/src'

_BADGE_TO_REPO_URL = {
    # Hard to implement.
    # code-landed_in_any_cr_repository: ???
    'code-landed_in_chromium_browser':
        'https://chromium.googlesource.com/chromium/src',
    'code-landed_in_angle':
        'https://chromium.googlesource.com/angle/angle',
    'code-landed_in_asop':
        #'https://chromium.googlesource.com/angle/angle',
        '',
    'code-landed_in_arc':
        'https://chromium.googlesource.com/arc',
    'code-landed_in_breakpad':
        'https://chromium.googlesource.com/breakpad/breakpad',
    'code-landed_in_catapult':
        'https://chromium.googlesource.com/catapult',
    'code-landed_in_chromeos':
        #'https://chromium.googlesource.com/angle/angle',
        '',
    'code-landed_in_crashpad':
        'https://chromium.googlesource.com/crashpad',
    'code-landed_in_dart':
        #'https://chromium.googlesource.com/angle/angle',
        '',
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
        'https://chromium.googlesource.com/v8',
    'code-landed_in_webm':
        'https://chromium.googlesource.com/webm',
}


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
  repo = LocalGitRepository(repo_url)
  for revision in revisions:
    changelog = repo.GetChangeLog(revision)
    match = _TBR_REGEX.search(changelog.description)
    if match:
      with lock:
        author_data[changelog.author.email] += 1


def NumberOfTBRAsigned(changelogs, author_data, lock):
  """Returns the number TBR assigned authors in a list of commits."""
  for changelog in changelogs:
    match = _TBR_REGEX.search(changelog.description)
    if match:
      tbr_assigneds = match.group(1).split(',')
      with lock:
        for tbr_assigned in tbr_assigneds:
          author_data[tbr_assigned] += 1


def GetAuthorDataInRepo(func, repo_url=None):
  repo_url = repo_url or _CHROMIUM_SRC
  lock = threading.Lock()
  commits_landed_in_repo = defaultdict(int)
  repository = LocalGitRepository(repo_url)
  # Get all the changelogs from the beginning.
  changelogs = repository.GetChangeLogs(None, None)

  tasks = []
  tasks.append({'function': func,
                'args': [changelogs, author_data, lock]})
  script_util.RunTasks(tasks)
  return [{'email': email, 'value': value}
          for email, value in author_data.iteritems()]


def ComputeCommitBadge():
  """Compute commit type of badges."""
  argparser = argparse.ArgumentParser(
      description='Compute commit type of badges')

  argparser.add_argument(
      'badge',
      help='The name of the commit badge')

  args = argparser.parse_args()

  author_data = GetAuthorDataInRepo(*GetFunctionAndRepoUrlForBadge(args.badge))
  return {'badge_name': args.badge,
          'data': author_data}


if __name__ == '__main__':
  badge_info = ComputeCommitBadge()
  print json.dumps(badge_info)
