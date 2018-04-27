# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides functions for git-related functions.

It has functions to:
  * Pull change logs for CLs.
  * Get Git Blame for a CL.
  * Get information for given revisions.
"""

import datetime

from common.findit_http_client import FinditHttpClient
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import time_util

_CHROMIUM_REPO_URL = 'https://chromium.googlesource.com/chromium/src.git'


def GetGitBlame(repo_url, revision, touched_file_path):
  """Gets git blames of touched_file.

  Args:
    repo_url (str): Url to the repo.
    revision (str): Revision for the change.
    touched_file_path (str): Full path of a file in change_log.
  """
  git_repo = CachedGitilesRepository(FinditHttpClient(), repo_url)
  return git_repo.GetBlame(touched_file_path, revision)


def PullChangeLogs(failure_info):
  """Pulls change logs for CLs.

  Args:
    failure_info (BaseFailureInfo): Output of pipeline
      DetectFirstFailurePipeline.run().

  Returns:
    A dict with the following form:
    {
      'git_hash_revision1': common.change_log.ChangeLog.ToDict(),
      ...
    }
  """
  git_repo = CachedGitilesRepository(FinditHttpClient(), _CHROMIUM_REPO_URL)

  change_logs = {}
  builds = failure_info.builds or {}
  for build in builds.values():
    for revision in build.blame_list:
      change_log = git_repo.GetChangeLog(revision)
      if not change_log:
        raise Exception('Failed to get change log for %s' % revision)

      change_logs[revision] = change_log.ToDict()

  return change_logs


def GetCLInfo(revisions):
  """Gets commit_positions and review urls for revisions."""
  git_repo = CachedGitilesRepository(FinditHttpClient(), _CHROMIUM_REPO_URL)
  cls = {}
  # TODO(crbug/767759): remove hard-coded 'chromium' when DEPS file parsing is
  # supported.
  for revision in revisions:
    cls[revision] = {'revision': revision, 'repo_name': 'chromium'}
    change_log = git_repo.GetChangeLog(revision)
    if change_log:
      cls[revision]['commit_position'] = (change_log.commit_position)
      cls[revision]['url'] = (
          change_log.code_review_url or change_log.commit_url)
      cls[revision]['author'] = change_log.author.email
  return cls


def GetCommitsBetweenRevisionsInOrder(start_revision,
                                      end_revision,
                                      ascending=True):
  """Gets the revisions between start_revision and end_revision.

  Args:
    start_revision (str): The revision for which to get changes after. This
        revision is not included in the returned list.
    end_revision (str): The last revision in the range to return.
    ascending (bool): Whether the commits should be in chronological order.

  Returns:
    A list of revisions sorted in order chronologically.
  """
  repo = CachedGitilesRepository(FinditHttpClient(), _CHROMIUM_REPO_URL)
  commits = repo.GetCommitsBetweenRevisions(start_revision, end_revision)

  if ascending:
    commits.reverse()
  return commits


def CountRecentCommits(repo_url,
                       ref='refs/heads/master',
                       time_period=datetime.timedelta(hours=1)):
  """Gets the number of commits that landed recently.

  By default, this function will count the commits landed in the master branch
  during last hour, but can be used to count the commits landed in any ref in
  the most recent period of any arbitrary size.

  Args:
    repo_url (str): Url to the repo.
    ref (str): ref to count commits on.
    time_period (datetime.delta): window of time in which to count commits.

  Returns:
    An integer representing the number of commits that landed in the last
    hour.
  """
  count = 0
  cutoff = time_util.GetUTCNow() - time_period
  git_repo = CachedGitilesRepository(FinditHttpClient(), repo_url)
  next_rev = ref
  while next_rev:
    # 100 is a reasonable size for a page.
    # This assumes that GetNChangeLogs returns changelogs in newer to older
    # order.
    logs, next_rev = git_repo.GetNChangeLogs(next_rev, 100)
    for log in logs:
      if log.committer.time >= cutoff:
        count += 1
      else:
        return count
  return count
