# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides functions for git-related functions.

It has functions to:
  * Pull change logs for CLs.
  * Get Git Blame for a CL.
  * Get information for given revisions.
"""

from common.findit_http_client import FinditHttpClient
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from services.parameters import CLKey
from services.parameters import DictOfCLKeys


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
    failure_info (dict): Output of pipeline DetectFirstFailurePipeline.run().

  Returns:
    A dict with the following form:
    {
      'git_hash_revision1': common.change_log.ChangeLog.ToDict(),
      ...
    }
  """
  git_repo = CachedGitilesRepository(
      FinditHttpClient(), 'https://chromium.googlesource.com/chromium/src.git')

  change_logs = {}
  for build in failure_info.get('builds', {}).values():
    for revision in build['blame_list']:
      change_log = git_repo.GetChangeLog(revision)
      if not change_log:
        raise Exception('Failed to get change log for %s' % revision)

      change_logs[revision] = change_log.ToDict()

  return change_logs


def GetCLInfo(revisions):
  """Gets commit_positions and review urls for revisions."""
  git_repo = CachedGitilesRepository(
      FinditHttpClient(), 'https://chromium.googlesource.com/chromium/src.git')
  cls = {}
  # TODO(crbug/767759): remove hard-coded 'chromium' when DEPS file parsing is
  # supported.
  for revision in revisions:
    cls[revision] = {'revision': revision, 'repo_name': 'chromium'}
    change_log = git_repo.GetChangeLog(revision)
    if change_log:
      cls[revision]['commit_position'] = (change_log.commit_position)
      cls[revision]['url'] = (change_log.code_review_url or
                              change_log.commit_url)

  return cls


def GetCLKeysFromCLInfo(cl_info):
  """Get a dict of CLKeys object from result of GetCLInfo."""
  cl_keys = DictOfCLKeys()
  for revision, info in cl_info.iteritems():
    cl_keys[revision] = CLKey(
        repo_name=info['repo_name'], revision=info['revision'])
  return cl_keys
