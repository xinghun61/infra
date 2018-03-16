# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""General functions for operating on commit positions and revisions."""

from common.findit_http_client import FinditHttpClient
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from services import step_util
from waterfall import build_util
from waterfall.flake import flake_constants

_GIT_REPO = CachedGitilesRepository(FinditHttpClient(),
                                    flake_constants.CHROMIUM_GIT_REPOSITORY_URL)


def GetRevisionFromCommitPosition(master_name, builder_name, step_name,
                                  commit_position):
  """Converts a commit position to a chromium revision.

  Args:
    master_name (str): The name of the master to query build info for.
    builder_name (str): The name of the builder to query build info for.
    step_name (str): The name of the step to check valid builds.
    commit_position (int): The commit position to retrieve the corresponding
        chromium revision for.

  Returns:
    (str) The chromium revision corresponding to the requested commit position.
  """
  lower_bound_build, upper_bound_build = (
      step_util.GetValidBoundingBuildsForStep(
          master_name, builder_name, step_name, None, None, commit_position))
  lower_bound_commit_position = lower_bound_build.commit_position
  upper_bound_commit_position = upper_bound_build.commit_position

  assert commit_position > lower_bound_commit_position
  assert commit_position <= upper_bound_commit_position

  lower_bound_revision = lower_bound_build.chromium_revision
  upper_bound_revision = upper_bound_build.chromium_revision
  revisions = _GIT_REPO.GetCommitsBetweenRevisions(lower_bound_revision,
                                                   upper_bound_revision)

  return revisions[upper_bound_commit_position - commit_position]
