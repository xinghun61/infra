# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import logging
import mock

from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from infra_api_clients import logdog_util
from model.wf_build import WfBuild
from services import swarming
from waterfall import build_util
from waterfall import buildbot
from waterfall.build_info import BuildInfo
from waterfall.test import wf_testcase


class MockBuild(object):

  def __init__(self, response):
    self.response = response


MOCK_BUILDS = [(None,
                MockBuild({
                    'tags': [
                        'swarming_tag:log_location:logdog://host/project/path'
                    ]
                }))]


def _MockedGetBuildInfo(master_name, builder_name, build_number):
  build = BuildInfo(master_name, builder_name, build_number)
  build.commit_position = (build_number + 1) * 10
  return 200, build


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

  def testBuildDataNotNeedUpdating(self):
    build = WfBuild.Create('m', 'b', 1)

    # Build is not completed yet but data is recent.
    build.data = 'dummy'
    build.completed = False
    build.last_crawled_time = self._TimeBeforeNowBySeconds(60)
    self.assertFalse(build_util._BuildDataNeedUpdating(build))

    # Build was completed and data is final.
    build.data = 'dummy'
    build.completed = True
    build.last_crawled_time = self._TimeBeforeNowBySeconds(360)
    self.assertFalse(build_util._BuildDataNeedUpdating(build))

  @mock.patch.object(
      build_util, '_GetLogLocationForBuild', return_value='location')
  def testGetBuildDataNotDownloadAgain(self, mock_location):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build = WfBuild.Create(master_name, builder_name, build_number)

    build.data = 'dummy'
    build.completed = False
    build.last_crawled_time = self._TimeBeforeNowBySeconds(60)
    build.log_location = 'location'
    build.put()

    build_util.DownloadBuildData(master_name, builder_name, build_number)

    expected_build_data = 'dummy'

    self.assertEqual(expected_build_data, build.data)
    mock_location.assert_has_called_once_with(expected_build_data)

  @mock.patch.object(
      build_util, '_GetLogLocationForBuild', return_value='location')
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

  @mock.patch.object(
      build_util, '_GetLogLocationForBuild', return_value='location')
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

  @mock.patch.object(
      build_util, '_GetLogLocationForBuild', return_value='location')
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

  def testGetBuildEndTime(self):
    cases = {
        'null': None,
        '1467740016': datetime.datetime(2016, 7, 5, 17, 33, 36),
    }
    for end_time, expected_time in cases.iteritems():
      master_name = 'm'
      builder_name = 'b'
      build_number = 123
      build = WfBuild.Create(master_name, builder_name, build_number)
      build.data = '{"times": [1467738821, %s]}' % end_time
      build.completed = True
      build.last_crawled_time = self._TimeBeforeNowBySeconds(10)
      build.put()

      self.assertEqual(
          expected_time,
          build_util.GetBuildEndTime(master_name, builder_name, build_number))

  @mock.patch.object(build_util, 'DownloadBuildData')
  def testGetBuildInfo(self, mocked_fn):
    build = WfBuild.Create('m', 'b', 123)
    build.data = json.dumps({
        'properties': [['got_revision', 'a_git_hash'],
                       ['got_revision_cp', 'refs/heads/master@{#12345}']],
    })
    mocked_fn.return_value = (200, build)

    _, build_info = build_util.GetBuildInfo('m', 'b', 123)
    self.assertEqual(build_info.chromium_revision, 'a_git_hash')

  @mock.patch.object(build_util, 'DownloadBuildData')
  def testGetBuildInfoNoUpdate(self, mocked_fn):
    build = WfBuild.Create('m', 'b', 123)
    build.completed = True
    build.data = json.dumps({
        'properties': [['got_revision', 'a_git_hash'],
                       ['got_revision_cp', 'refs/heads/master@{#12345}']],
    })
    mocked_fn.return_value = (200, build)

    _, build_info = build_util.GetBuildInfo('m', 'b', 123)
    self.assertEqual(build_info.chromium_revision, 'a_git_hash')

  @mock.patch.object(build_util, 'DownloadBuildData')
  def testGetBuildInfoBuildNotAvailable(self, mocked_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.data = {}
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
    build_info.result = buildbot.EXCEPTION
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

  def _PreviousBuilds(self, master_name, builder_name, build_number):
    builds = []
    for build in build_util.IteratePreviousBuildsFrom(master_name, builder_name,
                                                      build_number, 20):
      builds.append(build)
    return builds

  @mock.patch.object(build_util, 'GetBuildInfo')
  def testIteratePreviousBuildsFrom(self, mock_info):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    mock_info.side_effect = [(200,
                              _MockedGetBuildInfo(master_name, builder_name,
                                                  123)), (404, None)]

    self.assertEqual(
        1, len(self._PreviousBuilds(master_name, builder_name, build_number)))

  @mock.patch.object(build_util, 'GetBuildInfo')
  def testIteratePreviousBuildsFromFailed(self, mock_info):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    mock_info.side_effect = [(500, None)]

    with self.assertRaises(Exception):
      self.assertEqual([],
                       self._PreviousBuilds(master_name, builder_name,
                                            build_number))

  def testGetLogLocationForBuildNoneData(self):
    self.assertIsNone(build_util._GetLogLocationForBuild(None))

  def testGetLogLocationForBuildNoUsefulInfo(self):
    data_json = {
        'properties': [[
            'others', 'other_property', 'Annotation(LogDog Bootstrap)'
        ]]
    }
    self.assertIsNone(build_util._GetLogLocationForBuild(json.dumps(data_json)))

  def testGetLogLocationForBuildForBuildbotBuild(self):
    location = ('logdog://logs.chromium.org/chromium/bb/m/b/1/+/recipes/'
                'annotations')
    data_json = {
        'properties': [[
            'log_location', location, 'Annotation(LogDog Bootstrap)'
        ]]
    }
    self.assertEqual(location,
                     build_util._GetLogLocationForBuild(json.dumps(data_json)))

  @mock.patch.object(
      buildbucket_client, 'GetTryJobs', return_value=[('error', None)])
  def testGetLogLocationForBuildForLUCIBuildNoBuildbucketBuild(self, _):
    data_json = {
        'properties': [[
            'buildbucket', {
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

    self.assertIsNone(build_util._GetLogLocationForBuild(json.dumps(data_json)))

  @mock.patch.object(buildbucket_client, 'GetTryJobs', return_value=MOCK_BUILDS)
  def testGetLogLocationForBuildForLUCIBuild(self, _):
    data_json = {
        'properties': [[
            'buildbucket', {
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

    self.assertEqual('logdog://host/project/path',
                     build_util._GetLogLocationForBuild(json.dumps(data_json)))
