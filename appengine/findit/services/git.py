# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for git-related operations.

It provides functions to:
  * Get information for given revisions.
"""

from common.findit_http_client import FinditHttpClient
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from pipelines.pipeline_inputs_and_outputs import CLKey
from pipelines.pipeline_inputs_and_outputs import DictOfCLKeys


def GetCLInfo(revisions):
  """Gets commit_positions and review urls for revisions."""
  git_repo = CachedGitilesRepository(
      FinditHttpClient(), 'https://chromium.googlesource.com/chromium/src.git')
  cls = {}
  # TODO(crbug/767759): remove hard-coded 'chromium' when DEPS file parsing is
  # supported.
  for revision in revisions:
    cls[revision] = {'revision': revision, 'repo_name': u'chromium'}
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
