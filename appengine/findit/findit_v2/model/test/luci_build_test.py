# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from buildbucket_proto import common_pb2
from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.build_pb2 import BuilderID
from google.appengine.ext import ndb

from findit_v2.model import luci_build
from findit_v2.model.luci_build import ParseBuilderId
from findit_v2.model.luci_build import LuciFailedBuild
from findit_v2.services.context import Context
from findit_v2.services.failure_type import StepTypeEnum
from services import git
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
    res1 = LuciFailedBuild.GetBuildByNumber('chromium', 'ci', 'Linux Builder',
                                            legacy_build_number)
    self.assertEqual(build_id, res1.build_id)

    # Get entity by commit_position.
    res2 = LuciFailedBuild.query(
        ndb.AND(
            LuciFailedBuild.builder_id == 'chromium/ci/Linux Builder',
            LuciFailedBuild.gitiles_commit.commit_position ==
            commit_position)).fetch()
    self.assertEqual(1, len(res2))
    self.assertEqual(build_id, res2[0].build_id)

  def testParseBuilderId(self):
    builder = ParseBuilderId('chromium/ci/Linux Builder')
    self.assertEqual('chromium', builder.project)
    self.assertEqual('ci', builder.bucket)
    self.assertEqual('Linux Builder', builder.builder)

  @mock.patch.object(git, 'GetCommitPositionFromRevision', return_value=67890)
  def testSaveFailedBuild(self, _):
    builder = BuilderID(project='chromium', bucket='try', builder='linux-rel')
    build = Build(
        id=87654321, builder=builder, number=123, status=common_pb2.FAILURE)
    build.create_time.FromDatetime(datetime(2019, 4, 9))
    build.start_time.FromDatetime(datetime(2019, 4, 9, 0, 1))
    build.end_time.FromDatetime(datetime(2019, 4, 9, 1))

    context = Context(
        luci_project_name='project',
        gitiles_host='gitiles.host.com',
        gitiles_project='project/name',
        gitiles_ref='ref/heads/master',
        gitiles_id='git_sha')

    build_entity = luci_build.SaveFailedBuild(context, build,
                                              StepTypeEnum.COMPILE)

    self.assertIsNotNone(build_entity)

  def testGetBuilderIdString(self):
    self.assertEqual(
        'chromium/try/linux-rel',
        luci_build.GetBuilderIdString('chromium', 'try', 'linux-rel'))
