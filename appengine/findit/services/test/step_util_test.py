# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import logging
import mock

from parameterized import parameterized

from buildbucket_proto import common_pb2
from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.step_pb2 import Step

from common.waterfall import buildbucket_client
from infra_api_clients import logdog_util
from libs.test_results.gtest_test_results import GtestTestResults
from libs.test_results.webkit_layout_test_results import WebkitLayoutTestResults
from model.isolated_target import IsolatedTarget
from model.wf_build import WfBuild
from services import step_util
from services import swarming
from waterfall import build_util
from waterfall import waterfall_config
from waterfall.build_info import BuildInfo
from waterfall.test import wf_testcase


class MockWaterfallBuild(object):

  def __init__(self):
    self.build_id = None
    self.log_location = 'logdog://logs.chromium.org/chromium/buildbucket/path'


def _MockedGetBuildInfo(master_name, builder_name, build_number):
  build = BuildInfo(master_name, builder_name, build_number)
  build.commit_position = (build_number + 1) * 10
  build.result = (
      common_pb2.SUCCESS if build_number > 4 else common_pb2.INFRA_FAILURE)
  return build


class StepUtilTest(wf_testcase.WaterfallTestCase):

  def testGetLowerBoundBuildNumber(self):
    self.assertEqual(5, step_util._GetLowerBoundBuildNumber(5, 100))
    self.assertEqual(50, step_util._GetLowerBoundBuildNumber(None, 100, 200))
    self.assertEqual(100, step_util._GetLowerBoundBuildNumber(None, 600, 500))

  def testGetBoundingIsolatedTargets(self):
    lower_bound_commit_position = 1000
    upper_bound_commit_position = 1010
    requested_commit_position = 1005
    build_id = 10000
    target_name = 'browser_tests'
    master_name = 'm'
    builder_name = 'b'
    luci_name = 'chromium'
    bucket_name = 'ci'
    gitiles_host = 'chromium.googlesource.com'
    gitiles_project = 'chromium/src'
    gitiles_ref = 'refs/heads/master'
    gerrit_patch = ''
    lower_bound_revision = 'r1000'
    upper_bound_revision = 'r1010'

    lower_bound_target = IsolatedTarget.Create(
        build_id - 1, luci_name, bucket_name, master_name, builder_name,
        gitiles_host, gitiles_project, gitiles_ref, gerrit_patch, target_name,
        'hash_1', lower_bound_commit_position, lower_bound_revision)
    lower_bound_target.put()

    upper_bound_target = IsolatedTarget.Create(
        build_id, luci_name, bucket_name, master_name, builder_name,
        gitiles_host, gitiles_project, gitiles_ref, gerrit_patch, target_name,
        'hash_2', upper_bound_commit_position, upper_bound_revision)
    upper_bound_target.put()

    self.assertEqual((lower_bound_target, upper_bound_target),
                     step_util.GetBoundingIsolatedTargets(
                         master_name, builder_name, target_name,
                         requested_commit_position))

  @mock.patch.object(build_util, 'GetBuildInfo')
  def testGetValidBuildSearchAscendingWithinRange(self, mocked_get_build_info):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'

    invalid_build_100 = BuildInfo(master_name, builder_name, 100)
    invalid_build_101 = BuildInfo(master_name, builder_name, 101)
    valid_build_102 = BuildInfo(master_name, builder_name, 102)
    valid_build_102.commit_position = 1020

    mocked_get_build_info.side_effect = [
        invalid_build_100,
        invalid_build_101,
        valid_build_102,
    ]

    self.assertEqual(
        valid_build_102,
        step_util.GetValidBuild(master_name, builder_name, 100, step_name, True,
                                2))

  @mock.patch.object(build_util, 'GetBuildInfo')
  def testGetValidBuildSearchAscendingOutOfRange(self, mocked_get_build_info):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'

    invalid_build_100 = BuildInfo(master_name, builder_name, 100)
    invalid_build_101 = BuildInfo(master_name, builder_name, 101)
    valid_build_102 = BuildInfo(master_name, builder_name, 102)
    valid_build_102.commit_position = 1020

    mocked_get_build_info.side_effect = [
        invalid_build_100,
        invalid_build_101,
        valid_build_102,
    ]

    self.assertIsNone(
        step_util.GetValidBuild(master_name, builder_name, 100, step_name, True,
                                1))

  @mock.patch.object(build_util, 'GetBuildInfo')
  def testGetValidBuildSearchDescending(self, mocked_get_build_info):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'

    invalid_build_100 = BuildInfo(master_name, builder_name, 100)
    invalid_build_99 = BuildInfo(master_name, builder_name, 99)
    valid_build_98 = BuildInfo(master_name, builder_name, 98)
    valid_build_98.commit_position = 980

    mocked_get_build_info.side_effect = [
        invalid_build_100,
        invalid_build_99,
        valid_build_98,
    ]

    self.assertEqual(
        valid_build_98,
        step_util.GetValidBuild(master_name, builder_name, 100, step_name, True,
                                2))

  @mock.patch.object(
      swarming, 'CanFindSwarmingTaskFromBuildForAStep', return_value=True)
  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  def testGetValidBoundingBuildsForStepExactMatch(self, *_):
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', 0, 100, 30)
    self.assertEqual(1, lower_bound.build_number)
    self.assertEqual(2, upper_bound.build_number)

  @mock.patch.object(
      swarming, 'CanFindSwarmingTaskFromBuildForAStep', return_value=True)
  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  def testGetValidBoundingBuildsForStepCommitBeforeEarliestBuild(self, *_):
    lower_bound_build_number = 3
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', lower_bound_build_number, 100, 10)

    self.assertIsNone(lower_bound)
    self.assertEqual(lower_bound_build_number, upper_bound.build_number)

  @mock.patch.object(
      swarming, 'CanFindSwarmingTaskFromBuildForAStep', return_value=False)
  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  def testGetValidBoundingBuildsForStepCommitBeforeEarliestBuildInValid(
      self, *_):
    lower_bound_build_number = 3
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', lower_bound_build_number, 100, 10)

    self.assertIsNone(lower_bound)
    self.assertIsNone(upper_bound)

  @mock.patch.object(
      swarming, 'CanFindSwarmingTaskFromBuildForAStep', return_value=True)
  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  def testGetValidBoundingBuildsForStepCommitAfterLatestBuild(self, *_):
    upper_bound_build_number = 5
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', None, upper_bound_build_number, 10000)
    self.assertEqual(upper_bound_build_number, lower_bound.build_number)
    self.assertIsNone(upper_bound)

  @mock.patch.object(
      swarming, 'CanFindSwarmingTaskFromBuildForAStep', return_value=False)
  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  def testGetValidBoundingBuildsForStepCommitAfterLatestBuildInvalid(self, *_):
    upper_bound_build_number = 5
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', None, upper_bound_build_number, 10000)

    self.assertIsNone(lower_bound)
    self.assertIsNone(upper_bound)

  @mock.patch.object(
      swarming, 'CanFindSwarmingTaskFromBuildForAStep', return_value=True)
  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  def testGetValidBoundingBuildsForStepCommitRightAtUpperBound(self, *_):
    upper_bound_build_number = 4
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', None, upper_bound_build_number, 50)

    self.assertEqual(50, lower_bound.commit_position)
    self.assertEqual(50, upper_bound.commit_position)

  @mock.patch.object(
      swarming, 'CanFindSwarmingTaskFromBuildForAStep', return_value=True)
  @mock.patch.object(build_util, 'GetBuildInfo', _MockedGetBuildInfo)
  def testGetValidBoundingBuildsForStepCommitRightAtLowerBound(self, *_):
    upper_bound_build_number = 4
    lower_bound_build_number = 1
    lower_bound, upper_bound = step_util.GetValidBoundingBuildsForStep(
        'm', 'b', 's', lower_bound_build_number, upper_bound_build_number, 20)

    self.assertEqual(20, lower_bound.commit_position)
    self.assertEqual(20, upper_bound.commit_position)

  def testIsStepSupportedByFinditObjectNone(self):
    self.assertFalse(step_util.IsStepSupportedByFindit(None, 'step', 'm'))

  @mock.patch.object(
      waterfall_config, 'StepIsSupportedForMaster', return_value=False)
  def testStepNotSupportedByFindit(self, _):
    self.assertFalse(
        step_util.IsStepSupportedByFindit(
            WebkitLayoutTestResults(None), 'step', 'm'))

  def testIsStepSupportedByFinditOtherIsolatedScriptTest(self):
    self.assertFalse(
        step_util.IsStepSupportedByFindit(
            WebkitLayoutTestResults(None), 'telemetry_perf_tests', 'm'))

  @mock.patch.object(
      waterfall_config, 'StepIsSupportedForMaster', return_value=True)
  def testIsStepSupportedByFinditWebkitLayoutTests(self, _):
    self.assertTrue(
        step_util.IsStepSupportedByFindit(
            WebkitLayoutTestResults(None), 'webkit_layout_tests', 'm'))

  @mock.patch.object(
      waterfall_config, 'StepIsSupportedForMaster', return_value=True)
  def testIsStepSupportedByFinditGtests(self, _):
    self.assertTrue(
        step_util.IsStepSupportedByFindit(
            GtestTestResults(None), 'browser_tests', 'm'))

  @parameterized.expand([
      ({
          'build_return': Build(),
          'step_log_return': wf_testcase.SAMPLE_STEP_METADATA,
          'expected_step_metadata': wf_testcase.SAMPLE_STEP_METADATA
      },),
      ({
          'build_return': Build(),
          'step_log_return': None,
          'expected_step_metadata': None
      },),
      ({
          'build_return': None,
          'expected_step_metadata': None
      },),
  ])
  @mock.patch.object(step_util, 'GetStepLogFromBuildObject')
  @mock.patch.object(buildbucket_client, 'GetV2Build')
  def testGetStepMetadata(self, cases, mock_build, mock_step_log):
    mock_build.return_value = cases['build_return']
    # Function executes GetStepLogFromBuildObject
    if 'step_log_return' in cases:
      mock_step_log.return_value = cases['step_log_return']

    step_metadata = step_util.GetStepMetadata(123, 'step')

    self.assertEqual(cases['expected_step_metadata'], step_metadata)

  @mock.patch.object(
      logdog_util, '_GetAnnotationsProtoForPath', return_value='step')
  @mock.patch.object(
      logdog_util, '_GetStreamForStep', return_value='log_stream')
  @mock.patch.object(
      logdog_util,
      'GetStepLogLegacy',
      return_value=json.dumps(wf_testcase.SAMPLE_STEP_METADATA))
  @mock.patch.object(
      build_util, 'DownloadBuildData', return_value=MockWaterfallBuild())
  def testLegacyGetStepMetadata(self, *_):
    step_metadata = step_util.GetWaterfallBuildStepLog('m', 'b', 123, 's', None,
                                                       'step_metadata')
    self.assertEqual(step_metadata, wf_testcase.SAMPLE_STEP_METADATA)

  @mock.patch.object(
      build_util, 'DownloadBuildData', return_value=MockWaterfallBuild())
  @mock.patch.object(logdog_util, 'GetStepLogLegacy', return_value=':')
  def testMalformattedNinjaInfo(self, *_):
    step_metadata = step_util.GetWaterfallBuildStepLog(
        'm', 'b', 123, 's', None, 'json.output[ninja_info]')
    self.assertIsNone(step_metadata)

  @mock.patch.object(
      build_util, 'DownloadBuildData', return_value=MockWaterfallBuild())
  @mock.patch.object(
      logdog_util, '_GetAnnotationsProtoForPath', return_value=None)
  def testLegacyGetStepMetadataStepNone(self, *_):
    step_metadata = step_util.GetWaterfallBuildStepLog('m', 'b', 123, 's', None,
                                                       'step_metadata')
    self.assertIsNone(step_metadata)

  @mock.patch.object(
      build_util, 'DownloadBuildData', return_value=MockWaterfallBuild())
  @mock.patch.object(
      logdog_util, '_GetAnnotationsProtoForPath', return_value='step')
  @mock.patch.object(logdog_util, '_GetStreamForStep', return_value=None)
  def testLegacyGetStepMetadataStreamNone(self, *_):
    step_metadata = step_util.GetWaterfallBuildStepLog('m', 'b', 123, 's', None,
                                                       'step_metadata')
    self.assertIsNone(step_metadata)

  @mock.patch.object(
      step_util,
      'GetStepLogForLuciBuild',
      return_value=wf_testcase.SAMPLE_STEP_METADATA)
  @mock.patch.object(build_util, 'DownloadBuildData')
  def testLegacyGetStepMetadataFromLUCIBuild(self, mock_build, _):
    build = WfBuild.Create('m', 'b', 123)
    build.build_id = '8948240770002521488'
    build.put()
    mock_build.return_value = build
    step_metadata = step_util.GetWaterfallBuildStepLog('m', 'b', 123, 's', None,
                                                       'step_metadata')
    self.assertEqual(step_metadata, wf_testcase.SAMPLE_STEP_METADATA)

  @mock.patch.object(
      build_util, 'DownloadBuildData', return_value=MockWaterfallBuild())
  @mock.patch.object(
      logdog_util, '_GetAnnotationsProtoForPath', return_value='step')
  @mock.patch.object(logdog_util, '_GetStreamForStep', return_value='stream')
  @mock.patch.object(logdog_util, 'GetStepLogLegacy', return_value='log1/nlog2')
  def testGetStepLogStdio(self, *_):
    self.assertEqual(
        'log1/nlog2',
        step_util.GetWaterfallBuildStepLog('m', 'b', 123, 's', None))

  @mock.patch.object(
      build_util, 'DownloadBuildData', return_value=MockWaterfallBuild())
  @mock.patch.object(logdog_util, 'GetStepLogLegacy', return_value='log')
  @mock.patch.object(logging, 'error')
  def testGetStepLogNotJosonLoadable(self, mocked_log, *_):
    self.assertIsNone(
        step_util.GetWaterfallBuildStepLog('m', 'b', 123, 's', None,
                                           'step_metadata'))
    mocked_log.assert_called_with(
        'Failed to json load data for step_metadata. Data is: log.')

  @mock.patch.object(buildbucket_client, 'GetV2Build', return_value=None)
  def testGetStepLogForLuciBuildError(self, _):
    self.assertIsNone(step_util.GetStepLogForLuciBuild('87654321', 's', None))

  @mock.patch.object(step_util, '_GetStepLogViewUrl', return_value=None)
  @mock.patch.object(logdog_util, 'GetLogFromViewUrl')
  @mock.patch.object(buildbucket_client, 'GetV2Build')
  def testGetStepLogForLuciBuildNoViewUrl(self, mock_get_build, mock_get_log,
                                          _):
    build_id = '8945610992972640896'
    mock_log = common_pb2.Log()
    mock_log.name = 'step_metadata'
    mock_log.view_url = 'view_url'
    mock_step = Step()
    mock_step.name = 's'
    mock_step.logs.extend([mock_log])
    mock_build = Build()
    mock_build.id = int(build_id)
    mock_build.steps.extend([mock_step])
    mock_get_build.return_value = mock_build
    self.assertIsNone(
        step_util.GetStepLogForLuciBuild(build_id, 's', None, 'step_metadata'))
    self.assertFalse(mock_get_log.called)

  @mock.patch.object(
      step_util, '_ParseStepLogIfAppropriate', return_value='log')
  @mock.patch.object(logdog_util, 'GetLogFromViewUrl', return_value='log')
  @mock.patch.object(buildbucket_client, 'GetV2Build')
  def testGetStepLogForLuciBuild(self, mock_get_build, mock_get_log, _):
    build_id = '8945610992972640896'
    mock_log = common_pb2.Log()
    mock_log.name = 'step_metadata'
    mock_log.view_url = 'view_url'
    mock_step = Step()
    mock_step.name = 's'
    mock_step.logs.extend([mock_log])
    mock_build = Build()
    mock_build.id = int(build_id)
    mock_build.steps.extend([mock_step])
    mock_get_build.return_value = mock_build
    self.assertEqual(
        'log',
        step_util.GetStepLogForLuciBuild(build_id, 's', None, 'step_metadata'))
    mock_get_log.assert_called_once_with('view_url', None)

  def testGetStepLogViewUrlNoMatchingLog(self):
    build_id = 8945610992972640896
    mock_log = common_pb2.Log()
    mock_log.name = 'another_log'
    mock_log.view_url = 'view_url'
    mock_step1 = Step()
    mock_step1.name = 's1'
    mock_step1.logs.extend([mock_log])
    mock_step2 = Step()
    mock_step2.name = 's2'
    mock_step2.logs.extend([mock_log])
    mock_build = Build()
    mock_build.id = build_id
    mock_build.steps.extend([mock_step1, mock_step2])
    self.assertIsNone(step_util._GetStepLogViewUrl(mock_build, 's2', 'log'))

  @mock.patch.object(
      step_util,
      'GetWaterfallBuildStepLog',
      return_value={'canonical_step_name': 'unsupported_step1'})
  def testStepIsSupportedForMaster(self, _):
    master_name = 'master1'
    builder_name = 'b'
    build_number = 123
    step_name = 'unsupported_step1 on master1'
    self.assertFalse(
        step_util.StepIsSupportedForMaster(master_name, builder_name,
                                           build_number, step_name))

  def testStepIsSupportedForMasterCompile(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'compile'
    self.assertTrue(
        step_util.StepIsSupportedForMaster(master_name, builder_name,
                                           build_number, step_name))

  @mock.patch.object(step_util, 'GetWaterfallBuildStepLog')
  def testLegacyGetStepMetadataCached(self, mock_fn):
    mock_fn.side_effect = ['invalid', {'canonical_step_name': 'step_name'}]
    # Returns the invalid step_metadata but not cache it.
    self.assertEqual(
        'invalid',
        step_util.LegacyGetStepMetadata('m', 'b', 201,
                                        'step_name on a platform'))
    self.assertTrue(mock_fn.call_count == 1)
    # Returns the valid step_metadata and cache it.
    self.assertEqual({
        'canonical_step_name': 'step_name'
    }, step_util.LegacyGetStepMetadata('m', 'b', 201,
                                       'step_name on a platform'))
    self.assertTrue(mock_fn.call_count == 2)
    self.assertEqual({
        'canonical_step_name': 'step_name'
    }, step_util.LegacyGetStepMetadata('m', 'b', 201,
                                       'step_name on a platform'))
    self.assertTrue(mock_fn.call_count == 2)

  @mock.patch.object(buildbucket_client, 'GetV2Build', return_value=Build())
  @mock.patch.object(step_util, 'GetStepLogFromBuildObject')
  def testGetStepMetadataCached(self, mock_fn, *_):
    mock_fn.side_effect = [None, {'canonical_step_name': 'step_name'}]
    # Returns the invalid step_metadata but not cache it.
    self.assertEqual(None,
                     step_util.GetStepMetadata(123, 'step_name on a platform'))
    self.assertTrue(mock_fn.call_count == 1)
    # Returns the valid step_metadata and cache it.
    self.assertEqual({
        'canonical_step_name': 'step_name'
    }, step_util.GetStepMetadata(123, 'step_name on a platform'))
    self.assertTrue(mock_fn.call_count == 2)
    self.assertEqual({
        'canonical_step_name': 'step_name'
    }, step_util.GetStepMetadata(123, 'step_name on a platform'))
    self.assertTrue(mock_fn.call_count == 2)

  @mock.patch.object(
      step_util,
      'LegacyGetStepMetadata',
      return_value={'canonical_step_name': 'step_name'})
  def testLegacyGetCanonicalStep(self, _):
    self.assertEqual(
        'step_name',
        step_util.LegacyGetCanonicalStepName('m', 'b', 200,
                                             'step_name on a platform'))

  @parameterized.expand([({
      'canonical_step_name': 'step_name'
  }, 'step_name'), (None, 'step_name'), ({
      'a': 'b'
  }, None)])
  @mock.patch.object(step_util, 'GetStepMetadata')
  def testGetCanonicalStepName(self, step_metadata, expected_canonical_step,
                               mocked_get_step):
    mocked_get_step.return_value = step_metadata
    self.assertEqual(
        expected_canonical_step,
        step_util.GetCanonicalStepName(123, 'step_name (with patch)'))

  @mock.patch.object(
      step_util,
      'LegacyGetStepMetadata',
      return_value={'isolate_target_name': 'browser_tests'})
  def testLegacyGetIsolateTargetName(self, _):
    self.assertEqual(
        'browser_tests',
        step_util.LegacyGetIsolateTargetName(
            'm', 'b', 200, 'viz_browser_tests (with patch) on Android'))

  @mock.patch.object(step_util, 'LegacyGetStepMetadata', return_value=None)
  def testLegacyGetIsolateTargetNameStepMetadataIsNone(self, _):
    self.assertEqual(
        None,
        step_util.LegacyGetIsolateTargetName(
            'm', 'b', 200, 'viz_browser_tests (with patch) on Android'))

  @mock.patch.object(
      step_util, 'LegacyGetStepMetadata', return_value={'a': 'b'})
  def testLegacyGetIsolateTargetNameIsolateTargetNameIsMissing(self, _):
    self.assertEqual(
        None,
        step_util.LegacyGetIsolateTargetName(
            'm', 'b', 200, 'viz_browser_tests (with patch) on Android'))

  @parameterized.expand([({
      'isolate_target_name': 'isolate_target'
  }, 'isolate_target'), (None, None), ({
      'a': 'b'
  }, None)])
  @mock.patch.object(step_util, 'GetStepMetadata')
  def testGetIsolateTargetName(self, step_metadata, expected_isolate_target,
                               mocked_get_stepmeta):
    mocked_get_stepmeta.return_value = step_metadata
    self.assertEqual(expected_isolate_target,
                     step_util.GetIsolateTargetName(123, 'full step name'))

  @parameterized.expand([(wf_testcase.SAMPLE_STEP_METADATA, 'platform'),
                         (None, None)])
  @mock.patch.object(step_util, 'GetStepMetadata')
  def testGetPlatform(self, mock_fn_return, expected_platform, mock_fn):
    mock_fn.return_value = mock_fn_return
    self.assertEqual(expected_platform,
                     step_util.GetPlatform(123, 'builder_name', 'step_name'))

  @mock.patch.object(
      step_util,
      'GetStepMetadata',
      return_value=wf_testcase.SAMPLE_STEP_METADATA)
  def testGetPlatformCached(self, mock_fn):
    self.assertEqual('platform',
                     step_util.GetPlatform(123, 'builder_name', 'step_name'))
    self.assertEqual(1, mock_fn.call_count)
    self.assertEqual('platform',
                     step_util.GetPlatform(123, 'builder_name', 'step_name'))
    self.assertEqual(1, mock_fn.call_count)

  def testGetStepStartAndEndTime(self):
    build_id = '8945610992972640896'
    start_time = datetime.datetime(2019, 3, 6)
    end_time = datetime.datetime(2019, 3, 6, 0, 0, 10)
    step = Step()
    step.name = 's'
    step.start_time.FromDatetime(start_time)
    step.end_time.FromDatetime(end_time)
    build = Build()
    build.id = int(build_id)
    build.steps.extend([step])

    self.assertEqual((start_time, end_time),
                     step_util.GetStepStartAndEndTime(build, 's'))
    self.assertEqual((None, None), step_util.GetStepStartAndEndTime(
        build, 's2'))
