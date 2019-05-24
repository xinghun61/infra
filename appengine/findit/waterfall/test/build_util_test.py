# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock

from buildbucket_proto import common_pb2
from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.build_pb2 import BuilderID
from buildbucket_proto.rpc_pb2 import SearchBuildsResponse

from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from infra_api_clients import crrev
from model.isolated_target import IsolatedTarget
from model.wf_build import WfBuild
from services import git
from services import swarming
from waterfall import build_util
from waterfall import buildbot
from waterfall.build_info import BuildInfo
from waterfall.test import wf_testcase

# pylint:disable=unused-argument, unused-variable
# https://crbug.com/947753


class MockBuild(object):

  def __init__(self, response):
    self.response = response


MOCK_BUILDS = [(None,
                MockBuild({
                    'tags': [
                        'swarming_tag:log_location:logdog://host/project/path'
                    ]
                }))]


class BuildUtilTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 123
    self.buildbucket_id = '88123'
    self.step_name = 'browser_tests on platform'
    super(BuildUtilTest, self).setUp()

    with self.mock_urlfetch() as urlfetch:
      self.mocked_urlfetch = urlfetch

  @mock.patch.object(buildbucket_client, 'GetV2BuildByBuilderAndBuildNumber')
  def testDownloadBuildDataNoNeed(self, mock_get_build):
    build = WfBuild.Create('m', 'b', 123)
    build.build_id = '8000000123'
    build.put()
    build_util.DownloadBuildData('m', 'b', 123)
    self.assertFalse(mock_get_build.called)

  @mock.patch.object(buildbucket_client, 'GetV2BuildByBuilderAndBuildNumber')
  def testDownloadBuildData(self, mock_get_build):
    mock_get_build.return_value = Build(id=8000000123)
    build = build_util.DownloadBuildData('m', 'b', 123)
    self.assertIsNotNone(build)
    self.assertEqual('8000000123', build.build_id)

  @mock.patch.object(buildbucket_client, 'GetV2Build', return_value=Build())
  @mock.patch.object(buildbot, 'ExtractBuildInfoFromV2Build')
  @mock.patch.object(build_util, 'DownloadBuildData')
  def testGetBuildInfo(self, mocked_fn, mock_build_info, _):
    build = WfBuild.Create('m', 'b', 123)
    build.build_id = '8000000123'
    mocked_fn.return_value = build

    expected_build_info = BuildInfo('m', 'b', 123)
    expected_build_info.chromium_revision = 'a_git_hash'
    mock_build_info.return_value = expected_build_info

    build_info = build_util.GetBuildInfo('m', 'b', 123)
    self.assertEqual(build_info.chromium_revision, 'a_git_hash')

  @mock.patch.object(buildbucket_client, 'GetV2Build', return_value=Build())
  @mock.patch.object(buildbot, 'ExtractBuildInfoFromV2Build')
  @mock.patch.object(build_util, 'DownloadBuildData')
  def testGetBuildInfoNoUpdate(self, mocked_fn, mock_build_info, _):
    build = WfBuild.Create('m', 'b', 123)
    build.build_id = '8000000123'
    build.completed = True
    mocked_fn.return_value = build

    expected_build_info = BuildInfo('m', 'b', 123)
    expected_build_info.chromium_revision = 'a_git_hash'
    mock_build_info.return_value = expected_build_info

    build_info = build_util.GetBuildInfo('m', 'b', 123)
    self.assertEqual(build_info.chromium_revision, 'a_git_hash')

  def testGetFailureTypeUnknown(self):
    build_info = BuildInfo('m', 'b', 123)
    self.assertEqual(failure_type.UNKNOWN,
                     build_util.GetFailureType(build_info))

  def testGetFailureTypeInfra(self):
    build_info = BuildInfo('m', 'b', 123)
    build_info.result = common_pb2.INFRA_FAILURE
    build_info.failed_steps = ['compile']
    self.assertEqual(failure_type.INFRA, build_util.GetFailureType(build_info))

  def testGetFailureTypeCompile(self):
    build_info = BuildInfo('m', 'b', 123)
    build_info.failed_steps = ['compile']
    self.assertEqual(failure_type.COMPILE,
                     build_util.GetFailureType(build_info))

  def testGetFailureTypeTest(self):
    build_info = BuildInfo('m', 'b', 123)
    build_info.failed_steps = ['abc_tests']
    self.assertEqual(failure_type.TEST, build_util.GetFailureType(build_info))

  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=[10, 9])
  def testGetLatestBuildNumber(self, _):
    self.assertEqual(10, build_util.GetLatestBuildNumber('m', 'b'))

  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=None)
  def testGetLatestBuildNumberNoNetwork(self, _):
    self.assertIsNone(build_util.GetLatestBuildNumber('m', 'b'))

  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=[])
  def testGetLatestBuildNumberNoRecentCompletedBuilds(self, _):
    self.assertIsNone(build_util.GetLatestBuildNumber('m', 'b'))

  @mock.patch.object(IsolatedTarget, 'FindLatestIsolateByMaster')
  @mock.patch.object(crrev, 'RedirectByCommitPosition')
  def testGetLatestCommitPositionAndRevisionWithTargetsWithRevision(
      self, mocked_revision, mocked_target):
    master_name = 'm'
    builder_name = 'b'
    target_name = 't'
    expected_commit_position = 1000
    expected_revision = 'r1000'
    target = IsolatedTarget.Create(87654321, '', '', master_name, builder_name,
                                   '', '', '', '', target_name, '',
                                   expected_commit_position, expected_revision)
    mocked_target.return_value = [target]
    self.assertEqual((expected_commit_position, expected_revision),
                     build_util.GetLatestCommitPositionAndRevision(
                         master_name, builder_name, target_name))
    self.assertFalse(mocked_revision.called)

  @mock.patch.object(IsolatedTarget, 'FindLatestIsolateByMaster')
  @mock.patch.object(crrev, 'RedirectByCommitPosition')
  def testGetLatestCommitPositionAndRevisionWithTargets(self, mocked_revision,
                                                        mocked_target):
    master_name = 'm'
    builder_name = 'b'
    target_name = 't'
    expected_commit_position = 1000
    expected_revision = 'r1000'
    mocked_revision.return_value = {'git_sha': expected_revision}
    target = IsolatedTarget.Create(87654321, '', '', master_name, builder_name,
                                   '', '', '', '', target_name, '',
                                   expected_commit_position, None)
    mocked_target.return_value = [target]
    self.assertEqual((expected_commit_position, expected_revision),
                     build_util.GetLatestCommitPositionAndRevision(
                         master_name, builder_name, target_name))

  @mock.patch.object(git, 'GetCommitPositionFromRevision', return_value=100000)
  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testGetLatestCommitPositionWithBuild(self, mocked_build, _):
    master_name = 'm'
    builder_name = 'b'
    target_name = 't'
    expected_commit_position = 100000
    expected_revision = 'r100000'

    build = Build(
        builder=BuilderID(
            project='chromium', bucket='ci', builder=builder_name))
    build.input.gitiles_commit.project = 'chromium/src'
    build.input.gitiles_commit.host = 'chromium.googlesource.com'
    build.input.gitiles_commit.ref = 'refs/heads/master'
    build.input.gitiles_commit.id = expected_revision
    mocked_build.return_value = SearchBuildsResponse(builds=[build])

    self.assertEqual((expected_commit_position, expected_revision),
                     build_util.GetLatestCommitPositionAndRevision(
                         master_name, builder_name, target_name))

  def _PreviousBuilds(self, master_name, builder_name, build_id):
    builds = []
    for build in build_util.IteratePreviousBuildsFrom(master_name, builder_name,
                                                      build_id, 20):
      builds.append(build)
    return builds

  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testIteratePreviousBuildsFrom(self, mock_previous_build):
    master_name = 'm'
    builder_name = 'b'
    build_id = 80000000124

    mock_previous_build.side_effect = [
        SearchBuildsResponse(builds=[Build(id=80000000123)]),
        SearchBuildsResponse(builds=[]),
    ]

    self.assertEqual(
        1, len(self._PreviousBuilds(master_name, builder_name, build_id)))

  @mock.patch.object(buildbucket_client, 'GetV2Build', return_value=None)
  def testGetBuilderInfoForLUCIBuildNoBuildInfo(self, _):
    self.assertEqual((None, None),
                     build_util.GetBuilderInfoForLUCIBuild('9087654321'))

  @mock.patch.object(buildbucket_client, 'GetV2Build')
  def testGetBuilderInfoForLUCIBuild(self, mock_v2_build):
    build_id = 87654321
    mock_build = Build(
        id=build_id,
        builder=BuilderID(
            project='chromium',
            bucket='try',
            builder='b',
        ),
    )
    mock_v2_build.return_value = mock_build
    self.assertEqual(('chromium', 'try'),
                     build_util.GetBuilderInfoForLUCIBuild('87654321'))
