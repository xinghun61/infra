# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from services import step_util
from services.flake_failure import commit_position_util
from waterfall.build_info import BuildInfo
from waterfall.test.wf_testcase import WaterfallTestCase


class CommitPositionUtilTest(WaterfallTestCase):

  @mock.patch.object(CachedGitilesRepository, 'GetCommitsBetweenRevisions')
  @mock.patch.object(step_util, 'GetValidBoundingBuildsForStep')
  def testGetRevisionFromCommitPosition(self, mocked_builds, mocked_commits):
    lower_bound_build = BuildInfo('m', 'b', 123)
    lower_bound_build.commit_position = 996
    lower_bound_build.chromium_revision = 'r996'
    upper_bound_build = BuildInfo('m', 'b', 124)
    upper_bound_build.commit_position = 1000
    upper_bound_build.chromium_revision = 'r1000'

    mocked_builds.return_value = (lower_bound_build, upper_bound_build)
    mocked_commits.return_value = ['r1000', 'r999', 'r998', 'r997']

    self.assertEqual('r997',
                     commit_position_util.GetRevisionFromCommitPosition(
                         'm', 'b', 's', 997))
    self.assertEqual('r1000',
                     commit_position_util.GetRevisionFromCommitPosition(
                         'm', 'b', 's', 1000))
