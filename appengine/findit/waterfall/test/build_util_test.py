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

  def _TimeBeforeNowBySeconds(self, seconds):
    return datetime.datetime.utcnow() - datetime.timedelta(0, seconds, 0)

  def testBuildDataNeedUpdating(self):
    build = WfBuild.Create('m', 'b', 1)

    # Build data is not available.
    self.assertTrue(build_util._BuildDataNeedUpdating(build))

    # Build was not completed and data is not recent.
    build.data = 'dummy'
    build.completed = False
    build.last_crawled_time = self._TimeBeforeNowBySeconds(360)
    self.assertTrue(build_util._BuildDataNeedUpdating(build))

  @mock.patch.object(build_util, '_GetBuildIDForLUCIBuild', return_value=None)
  @mock.patch.object(
      build_util, '_GetLogLocationForBuildbotBuild', return_value='location')
  @mock.patch.object(
      buildbot,
      'GetBuildDataFromMilo',
      return_value=(200, 'Test get build data from build master'))
  def testGetBuildDataFromMilo(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    _, build = build_util.DownloadBuildData(master_name, builder_name,
                                            build_number)

    expected_build_data = 'Test get build data from build master'

    self.assertEqual(expected_build_data, build.data)

  @mock.patch.object(build_util, '_GetBuildIDForLUCIBuild', return_value=None)
  @mock.patch.object(
      build_util, '_GetLogLocationForBuildbotBuild', return_value='location')
  @mock.patch.object(
      buildbot,
      'GetBuildDataFromMilo',
      return_value=(200, 'Test get build data from milo'))
  def testDownloadBuildDataSourceFromBM(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.put()

    build_util.DownloadBuildData(master_name, builder_name, build_number)

    self.assertEqual(build.data, 'Test get build data from milo')

  @mock.patch.object(build_util, '_GetBuildIDForLUCIBuild', return_value=None)
  @mock.patch.object(
      build_util, '_GetLogLocationForBuildbotBuild', return_value='location')
  @mock.patch.object(
      buildbot,
      'GetBuildDataFromMilo',
      return_value=(200, 'Test get build data from milo updated'))
  def testDownloadBuildDataSourceFromBMUpateBuildData(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.data = 'Original build data'
    build.last_crawled_time = self._TimeBeforeNowBySeconds(360)
    build.put()

    build_util.DownloadBuildData(master_name, builder_name, build_number)

    self.assertEqual(build.data, 'Test get build data from milo updated')

  @mock.patch.object(buildbucket_client, 'GetV2Build', return_value=Build())
  @mock.patch.object(buildbot, 'ExtractBuildInfoFromV2Build')
  @mock.patch.object(build_util, 'DownloadBuildData')
  def testGetBuildInfo(self, mocked_fn, mock_build_info, _):
    build = WfBuild.Create('m', 'b', 123)
    build.build_id = '8000000123'
    mocked_fn.return_value = (200, build)

    expected_build_info = BuildInfo('m', 'b', 123)
    expected_build_info.chromium_revision = 'a_git_hash'
    mock_build_info.return_value = expected_build_info

    _, build_info = build_util.GetBuildInfo('m', 'b', 123)
    self.assertEqual(build_info.chromium_revision, 'a_git_hash')

  @mock.patch.object(buildbucket_client, 'GetV2Build', return_value=Build())
  @mock.patch.object(buildbot, 'ExtractBuildInfoFromV2Build')
  @mock.patch.object(build_util, 'DownloadBuildData')
  def testGetBuildInfoNoUpdate(self, mocked_fn, mock_build_info, _):
    build = WfBuild.Create('m', 'b', 123)
    build.build_id = '8000000123'
    build.completed = True
    mocked_fn.return_value = (200, build)

    expected_build_info = BuildInfo('m', 'b', 123)
    expected_build_info.chromium_revision = 'a_git_hash'
    mock_build_info.return_value = expected_build_info

    _, build_info = build_util.GetBuildInfo('m', 'b', 123)
    self.assertEqual(build_info.chromium_revision, 'a_git_hash')

  @mock.patch.object(build_util, 'DownloadBuildData')
  def testGetBuildInfoBuildNotAvailable(self, mocked_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build = WfBuild.Create(master_name, builder_name, build_number)
    mocked_fn.return_value = (404, build)

    self.assertEquals((404, None),
                      build_util.GetBuildInfo(master_name, builder_name,
                                              build_number))

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

  @mock.patch.object(swarming, 'ListSwarmingTasksDataByTags')
  def testFindValidBuildNumberForStepNearby(self, mock_list_fn):
    # pylint: disable=unused-argument
    def ListFnImpl(http, master, builder, build_number, step):
      if build_number == 8:
        return ['foo']
      return []

    mock_list_fn.side_effect = ListFnImpl
    self.assertEqual(
        8, build_util.FindValidBuildNumberForStepNearby('m', 'b', 's', 5))

  @mock.patch.object(swarming, 'ListSwarmingTasksDataByTags')
  def testFindValidBuildNumberForStepNearbyWithExcluded(self, mock_list_fn):
    # pylint: disable=unused-argument
    def ListFnImpl(http, master, builder, build_number, step):
      if build_number == 8 or build_number == 6:
        return ['foo']
      return []

    mock_list_fn.side_effect = ListFnImpl
    self.assertEqual(
        8, build_util.FindValidBuildNumberForStepNearby('m', 'b', 's', 5, [6]))

  @mock.patch.object(swarming, 'ListSwarmingTasksDataByTags', return_value=[])
  def testFindValidBuildNumberForStepNearbyWhenNoneValid(self, _):
    self.assertEqual(
        None, build_util.FindValidBuildNumberForStepNearby('m', 'b', 's', 5))

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

  def testGetLogLocationForBuildNoneData(self):
    self.assertIsNone(build_util._GetLogLocationForBuildbotBuild(None))

  def testGetLogLocationForBuildNoUsefulInfo(self):
    data_json = {
        'properties': [[
            'others', 'other_property', 'Annotation(LogDog Bootstrap)'
        ]]
    }
    self.assertIsNone(
        build_util._GetLogLocationForBuildbotBuild(json.dumps(data_json)))

  def testGetLogLocationForBuildForBuildbotBuild(self):
    location = ('logdog://logs.chromium.org/chromium/bb/m/b/1/+/recipes/'
                'annotations')
    data_json = {
        'properties': [[
            'log_location', location, 'Annotation(LogDog Bootstrap)'
        ]]
    }
    self.assertEqual(
        location,
        build_util._GetLogLocationForBuildbotBuild(json.dumps(data_json)))

  def testGetBuildIDForLUCIBuildNoneData(self):
    self.assertIsNone(build_util._GetBuildIDForLUCIBuild(None))

  def testGetBuildIDForLUCIBuildNoBuildbucket(self):
    data_json = {'properties': []}
    self.assertIsNone(build_util._GetBuildIDForLUCIBuild(json.dumps(data_json)))

  @mock.patch.object(buildbucket_client, 'GetTryJobs', return_value=MOCK_BUILDS)
  def testGetBuildIDForLUCIBuild(self, _):
    data_json = {
        'properties': [[
            'buildbucket',
            {
                'hostname': 'cr-buildbucket.appspot.com',
                'build': {
                    'created_ts':
                        1524589900472560,
                    'tags': ['builder:Linux Builder (dbg)',],
                    'bucket':
                        'luci.chromium.ci',
                    'created_by':
                        'user:luci-scheduler@appspot.gserviceaccount.com',
                    'project':
                        'chromium',
                    'id':
                        '8948345336480880560'
                }
            }, 'setup_build'
        ]]
    }

    self.assertEqual('8948345336480880560',
                     build_util._GetBuildIDForLUCIBuild(json.dumps(data_json)))

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
