# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from google.appengine.ext import ndb

from findit_v2.model.luci_build import ParseBuilderId
from findit_v2.model.luci_build import LuciFailedBuild
from findit_v2.model.luci_build import LuciRerunBuild
from findit_v2.services.failure_type import StepTypeEnum
from waterfall.test import wf_testcase


class LuciFailedBuildTest(wf_testcase.WaterfallTestCase):

  def testCreateLuciFailedBuildForCompileFailure(self):
    build_id = 87654321
    commit_position = 65432
    legacy_build_number = 12345
    build = LuciFailedBuild.Create(
        luci_project='chromium',
        luci_bucket='ci',
        luci_builder='Linux Builder',
        build_id=build_id,
        legacy_build_number=legacy_build_number,
        gitiles_host='chromium.googlesource.com',
        gitiles_project='chromium/src',
        gitiles_ref='refs/heads/master',
        gitiles_id='git_hash',
        commit_position=commit_position,
        status=20,
        create_time=datetime(2019, 3, 28),
        start_time=datetime(2019, 3, 28, 0, 1),
        end_time=datetime(2019, 3, 28, 1),
        build_failure_type=StepTypeEnum.COMPILE)
    build.put()

    # Get entity by build_id.
    build = LuciFailedBuild.get_by_id(build_id)
    self.assertIsNotNone(build)
    self.assertEqual(StepTypeEnum.COMPILE, build.build_failure_type)
    self.assertEqual(commit_position, build.gitiles_commit.commit_position)
    self.assertEqual('chromium/ci', build.bucket_id)
    self.assertEqual('chromium/ci/Linux Builder', build.builder_id)

    # Get entity by build number.
    res1 = LuciFailedBuild.query(
        ndb.AND(LuciFailedBuild.builder_id == 'chromium/ci/Linux Builder',
                LuciFailedBuild.legacy_build_number ==
                legacy_build_number)).fetch()
    self.assertEqual(1, len(res1))
    self.assertEqual(build_id, res1[0].build_id)

    # Get entity by commit_position.
    res2 = LuciFailedBuild.query(
        ndb.AND(
            LuciFailedBuild.builder_id == 'chromium/ci/Linux Builder',
            LuciFailedBuild.gitiles_commit.commit_position ==
            commit_position)).fetch()
    self.assertEqual(1, len(res2))
    self.assertEqual(build_id, res2[0].build_id)

  def testLuciRerunBuild(self):
    build_id = 1234567890
    commit_position = 65432

    LuciRerunBuild.Create(
        luci_project='chromium',
        luci_bucket='ci',
        luci_builder='Linux Builder',
        build_id=build_id,
        legacy_build_number=11111,
        gitiles_host='chromium.googlesource.com',
        gitiles_project='chromium/src',
        gitiles_ref='refs/heads/master',
        gitiles_id='git_hash',
        commit_position=commit_position,
        status=1,
        create_time=datetime(2019, 3, 28),
        build_failure_type=StepTypeEnum.COMPILE,
        referred_build_id=87654321).put()

    rerun_build = LuciRerunBuild.get_by_id(build_id)
    self.assertIsNotNone(rerun_build)

  def testParseBuilderId(self):
    expected_res = {
        'project': 'chromium',
        'bucket': 'ci',
        'builder': 'Linux Builder',
    }

    self.assertEqual(expected_res, ParseBuilderId('chromium/ci/Linux Builder'))
