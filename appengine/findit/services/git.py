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
from datetime import timedelta
import logging

from common import constants
from common.findit_http_client import FinditHttpClient
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs.gitiles.gitiles_repository import (GitilesRepository as
                                             NonCachedGitilesRepository)
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


def PullChangeLogs(start_revision, end_revision, **kwargs):
  """Pulls change logs for CLs between start_revision and end_revision.

  Args:
    start_revision (str): Start revision of the range, excluded.
    end_revision (str): End revision of the range, included. If end_revision is
      None, pulls all changes after start_revision.
    kwargs(dict): Keyword arguments passed as additional params for the query.
  Returns:
    A dict with the following form:
    {
      'git_hash_revision1': common.change_log.ChangeLog.ToDict(),
      ...
    }
  """
  if not start_revision:
    return {}

  git_repo = CachedGitilesRepository(FinditHttpClient(), _CHROMIUM_REPO_URL)
  change_logs = {}

  change_log_list = git_repo.GetChangeLogs(start_revision, end_revision,
                                           **kwargs)

  for change_log in change_log_list:
    change_logs[change_log.revision] = change_log

  return change_logs


# TODO(crbug.com/841581): Convert return value to DTO.
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


def GetCodeReviewInfoForACommit(_repo_name, revision):
  """Returns change info of the given revision.

  Returns commit position, code-review url, host and change_id.
  """
  # TODO(stgao): get repo url at runtime based on the given repo name.
  repo = CachedGitilesRepository(FinditHttpClient(), _CHROMIUM_REPO_URL)
  change_log = repo.GetChangeLog(revision)
  if not change_log:
    return {}
  return {
      'commit_position': change_log.commit_position,
      'code_review_url': change_log.code_review_url,
      'review_server_host': change_log.review_server_host,
      'review_change_id': change_log.review_change_id,
      'author': change_log.author.ToDict(),
      'committer': change_log.committer.ToDict()
  }


def GetCommitPositionFromRevision(revision):
  """Returns the corresponding commit position given a git revision."""
  return GetCLInfo([revision]).get(revision, {}).get('commit_position')


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
  git_repo = NonCachedGitilesRepository(FinditHttpClient(), repo_url)
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


def _GetAuthor(revision):
  git_repo = CachedGitilesRepository(FinditHttpClient(), _CHROMIUM_REPO_URL)
  change_log = git_repo.GetChangeLog(revision)
  return change_log.author if change_log else None


def GetCommitsBySameAutherAfterRevision(revision):
  """Gets later changes that are written by the given revision's author."""
  author = _GetAuthor(revision)
  if not author:
    return []

  author_email = author.email
  later_changes = PullChangeLogs(revision, None, author=author_email)
  return later_changes.keys()


def IsAuthoredByNoAutoRevertAccount(revision):
  """Returns True if
    - the change is an auto roll;
    - the change is an auto-committed change by an author whose changes should
      not be auto-reverted.
  """
  author = _GetAuthor(revision)
  if not author:
    return False

  author_email = author.email
  return (constants.AUTO_ROLLER_ACCOUNT_PATTERN.match(author_email) or
          author_email in constants.NO_AUTO_COMMIT_REVERT_ACCOUNTS)


def ChangeCommittedWithinTime(revision, hours=24):
  """Returns True if the change was committed within the time given."""
  delta = timedelta(hours=hours)
  git_repo = CachedGitilesRepository(FinditHttpClient(), _CHROMIUM_REPO_URL)
  change_log = git_repo.GetChangeLog(revision)
  culprit_commit_time = change_log.committer.time

  in_time = time_util.GetUTCNow() - culprit_commit_time < delta

  if not in_time:
    logging.info(
        'Culprit %s was committed over %d hours ago, stop auto '
        'commit.', revision, hours)

  return in_time
