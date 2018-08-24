# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import mock
import os

from common.waterfall import failure_type
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild
from services import ci_failure
from services import monitoring
from services.parameters import BaseFailedSteps
from services.parameters import CompileFailureInfo
from services.parameters import FailureInfoBuilds
from waterfall import buildbot
from waterfall import build_util
from waterfall.test import wf_testcase


class MockBuildInfo(object):

  def __init__(self, result, failed_steps):
    self.result = result
    self.failed_steps = failed_steps


class CIFailureServicesTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(CIFailureServicesTest, self).setUp()

    with self.mock_urlfetch() as urlfetch:
      self.mocked_urlfetch = urlfetch

  def _TimeBeforeNowBySeconds(self, seconds):
    return datetime.datetime.utcnow() - datetime.timedelta(0, seconds, 0)

  def _CreateAndSaveWfAnanlysis(self, master_name, builder_name, build_number,
                                status):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = status
    analysis.put()

  def _GetBuildData(self, master_name, builder_name, build_number):
    file_name = os.path.join(
        os.path.dirname(__file__), 'data',
        '%s_%s_%d.json' % (master_name, builder_name, build_number))
    with open(file_name, 'r') as f:
      return f.read()

  @mock.patch.object(build_util, 'GetBuildInfo', return_value=(500, None))
  def testFailedToExtractBuildInfo(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    failed_steps = {'a': {'current_failure': 124, 'first_failure': 124}}
    builds = {
        124: {
            'chromium_revision': 'some_git_hash',
            'blame_list': ['some_git_hash']
        }
    }
    failed_steps = BaseFailedSteps.FromSerializable(failed_steps)
    builds = FailureInfoBuilds.FromSerializable(builds)

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    failure_info = CompileFailureInfo(failed_steps=failed_steps, builds=builds)
    with self.assertRaises(Exception):
      failure_info = ci_failure.CheckForFirstKnownFailure(
          master_name, builder_name, build_number, failure_info)

    self.assertEqual(failed_steps, failure_info.failed_steps)

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testStopLookingBackIfAllFailedStepsPassedInLastBuild(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    failed_steps = {
        'a': {
            'current_failure': 124,
            'first_failure': 124,
            'supported': True
        }
    }
    builds = {
        124: {
            'chromium_revision': 'some_git_hash',
            'blame_list': ['some_git_hash']
        }
    }
    failed_steps = BaseFailedSteps.FromSerializable(failed_steps)
    builds = FailureInfoBuilds.FromSerializable(builds)
    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    # Setup build data for builds:
    mock_fn.side_effect = [(200,
                            self._GetBuildData(master_name, builder_name, 123))]

    expected_failed_steps = {
        'a': {
            'last_pass': 123,
            'current_failure': 124,
            'first_failure': 124,
            'supported': True
        }
    }

    expected_builds = {
        124: {
            'chromium_revision': 'some_git_hash',
            'blame_list': ['some_git_hash']
        },
        123: {
            'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07',
            'blame_list': ['64c72819e898e952103b63eabc12772f9640af07']
        }
    }

    failure_info = CompileFailureInfo(failed_steps=failed_steps, builds=builds)
    failure_info = ci_failure.CheckForFirstKnownFailure(
        master_name, builder_name, build_number, failure_info)

    self.assertEqual(expected_failed_steps,
                     failure_info.failed_steps.ToSerializable())
    self.assertEqual(expected_builds, failure_info.builds.ToSerializable())

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testStopLookingBackIfFindTheFirstBuild(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 2
    failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 2,
            'supported': True
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 2,
            'supported': True
        }
    }
    builds = {
        '2': {
            'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': ['5934404dc5392ab3ae2c82b52b366889fb858d91']
        }
    }
    failed_steps = BaseFailedSteps.FromSerializable(failed_steps)
    builds = FailureInfoBuilds.FromSerializable(builds)
    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    # Setup build data for builds:
    mock_fn.side_effect = [(200, self._GetBuildData(
        master_name, builder_name, 1)), (200,
                                         self._GetBuildData(
                                             master_name, builder_name, 0))]

    expected_failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 0,
            'last_pass': None,
            'supported': True
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 0,
            'last_pass': None,
            'supported': True
        }
    }

    expected_builds = {
        2: {
            'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': ['5934404dc5392ab3ae2c82b52b366889fb858d91']
        },
        1: {
            'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': ['5934404dc5392ab3ae2c82b52b366889fb858d91']
        },
        0: {
            'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': ['5934404dc5392ab3ae2c82b52b366889fb858d91']
        },
    }
    failure_info = CompileFailureInfo(failed_steps=failed_steps, builds=builds)

    ci_failure.CheckForFirstKnownFailure(master_name, builder_name,
                                         build_number, failure_info)

    self.assertEqual(expected_failed_steps,
                     failure_info.failed_steps.ToSerializable())
    self.assertEqual(expected_builds, failure_info.builds.ToSerializable())

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testLookBackUntilGreenBuild(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    failed_steps = {
        'net_unittests': {
            'current_failure': 123,
            'first_failure': 123,
            'supported': True
        },
        'unit_tests': {
            'current_failure': 123,
            'first_failure': 123,
            'supported': True
        }
    }
    builds = {
        123: {
            'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07',
            'blame_list': ['64c72819e898e952103b63eabc12772f9640af07']
        }
    }
    failed_steps = BaseFailedSteps.FromSerializable(failed_steps)
    builds = FailureInfoBuilds.FromSerializable(builds)

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    # Setup build data for builds:
    # 122: mock a build in datastore to ensure it is not fetched again.
    build = WfBuild.Create(master_name, builder_name, 122)
    build.data = self._GetBuildData(master_name, builder_name, 122)
    build.completed = True
    build.put()
    # 121: mock a build in datastore to ensure it is updated.
    build = WfBuild.Create(master_name, builder_name, 121)
    build.data = 'Blow up if used!'
    build.last_crawled_time = self._TimeBeforeNowBySeconds(7200)
    build.completed = False
    build.put()

    mock_fn.side_effect = [(200,
                            self._GetBuildData(master_name, builder_name, 121))]

    expected_failed_steps = {
        'net_unittests': {
            'last_pass': 122,
            'current_failure': 123,
            'first_failure': 123,
            'supported': True
        },
        'unit_tests': {
            'last_pass': 121,
            'current_failure': 123,
            'first_failure': 122,
            'supported': True
        }
    }

    expected_builds = {
        123: {
            'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07',
            'blame_list': ['64c72819e898e952103b63eabc12772f9640af07']
        },
        122: {
            'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': ['5934404dc5392ab3ae2c82b52b366889fb858d91']
        },
        121: {
            'chromium_revision':
                '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': [
                '2fe8767f011a20ed8079d3aba7008acd95842f79',
                'c0ed134137c98c2935bf32e85f74d4e94c2b980d',
                '63820a74b4b5a3e6707ab89f92343e7fae7104f0'
            ]
        }
    }

    failure_info = CompileFailureInfo(failed_steps=failed_steps, builds=builds)
    ci_failure.CheckForFirstKnownFailure(master_name, builder_name,
                                         build_number, failure_info)
    self.assertEqual(expected_failed_steps,
                     failure_info.failed_steps.ToSerializable())
    self.assertEqual(expected_builds, failure_info.builds.ToSerializable())

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testCheckForFirstKnownFailureHitBuildNumberGap(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    failed_steps = {
        'net_unittests': {
            'current_failure': 123,
            'first_failure': 123,
            'supported': True
        },
        'unit_tests': {
            'current_failure': 123,
            'first_failure': 123,
            'supported': True
        }
    }
    builds = {
        123: {
            'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07',
            'blame_list': ['64c72819e898e952103b63eabc12772f9640af07']
        }
    }
    failed_steps = BaseFailedSteps.FromSerializable(failed_steps)
    builds = FailureInfoBuilds.FromSerializable(builds)

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    # Setup build data for builds:
    # 122: mock a gap.
    build = WfBuild.Create(master_name, builder_name, 122)
    build.data = {}
    build.completed = False
    build.put()
    # 121: mock a build in datastore to ensure it is updated.
    build = WfBuild.Create(master_name, builder_name, 121)
    build.data = 'Blow up if used!'
    build.last_crawled_time = self._TimeBeforeNowBySeconds(7200)
    build.completed = False
    build.put()

    mock_fn.side_effect = [(404, None), (200,
                                         self._GetBuildData(
                                             master_name, builder_name, 121))]

    expected_failed_steps = {
        'net_unittests': {
            'last_pass': 121,
            'current_failure': 123,
            'first_failure': 123,
            'supported': True
        },
        'unit_tests': {
            'last_pass': 121,
            'current_failure': 123,
            'first_failure': 123,
            'supported': True
        }
    }

    expected_builds = {
        123: {
            'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07',
            'blame_list': ['64c72819e898e952103b63eabc12772f9640af07']
        },
        121: {
            'chromium_revision':
                '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': [
                '2fe8767f011a20ed8079d3aba7008acd95842f79',
                'c0ed134137c98c2935bf32e85f74d4e94c2b980d',
                '63820a74b4b5a3e6707ab89f92343e7fae7104f0'
            ]
        }
    }

    failure_info = CompileFailureInfo(failed_steps=failed_steps, builds=builds)
    ci_failure.CheckForFirstKnownFailure(master_name, builder_name,
                                         build_number, failure_info)

    self.assertEqual(expected_failed_steps,
                     failure_info.failed_steps.ToSerializable())
    self.assertEqual(expected_builds, failure_info.builds.ToSerializable())

  @mock.patch.object(ci_failure, '_StepIsSupportedForMaster', return_value=True)
  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testGetBuildFailureInfo(self, mock_fn, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.PENDING)

    mock_fn.return_value = (200,
                            self._GetBuildData(master_name, builder_name,
                                               build_number))

    failure_info, should_proceed = ci_failure.GetBuildFailureInfo(
        master_name, builder_name, build_number)

    expected_failure_info = {
        'failed': True,
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'is_luci': None,
        'buildbucket_bucket': None,
        'buildbucket_id': None,
        'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07',
        'builds': {
            build_number: {
                'blame_list': ['64c72819e898e952103b63eabc12772f9640af07'],
                'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07'
            }
        },
        'failed_steps': {
            'abc_test': {
                'current_failure': build_number,
                'first_failure': build_number,
                'supported': True
            }
        },
        'failure_type': failure_type.TEST,
        'parent_mastername': None,
        'parent_buildername': None,
    }

    self.assertEqual(expected_failure_info, failure_info)
    self.assertTrue(should_proceed)

  @mock.patch.object(build_util, 'GetBuildInfo', return_value=(500, None))
  @mock.patch.object(monitoring, 'OnWaterfallAnalysisStateChange')
  def testGetBuildFailureInfoFailedGetBuildInfo(self, mock_monitoring, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.PENDING)

    failure_info, should_proceed = ci_failure.GetBuildFailureInfo(
        master_name, builder_name, build_number)

    self.assertEqual({}, failure_info)
    self.assertFalse(should_proceed)
    mock_monitoring.assert_called_once_with(
        master_name='m',
        builder_name='b',
        failure_type='unknown',
        canonical_step_name='unknown',
        isolate_target_name='unknown',
        status='Error',
        analysis_type='Pre-Analysis')

  @mock.patch.object(build_util, 'GetBuildInfo', return_value=(404, None))
  @mock.patch.object(monitoring, 'OnWaterfallAnalysisStateChange')
  def testGetBuildFailureInfo404(self, mock_monitoring, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.PENDING)

    failure_info, should_proceed = ci_failure.GetBuildFailureInfo(
        master_name, builder_name, build_number)

    self.assertEqual({}, failure_info)
    self.assertFalse(should_proceed)
    mock_monitoring.assert_called_once_with(
        master_name='m',
        builder_name='b',
        failure_type='unknown',
        canonical_step_name='unknown',
        isolate_target_name='unknown',
        status='Skipped',
        analysis_type='Pre-Analysis')

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  @mock.patch.object(monitoring, 'OnWaterfallAnalysisStateChange')
  def testGetBuildFailureInfoBuildSuccess(self, mock_monitoring, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.PENDING)

    mock_fn.return_value = (200,
                            self._GetBuildData(master_name, builder_name,
                                               build_number))

    failure_info, should_proceed = ci_failure.GetBuildFailureInfo(
        master_name, builder_name, build_number)

    expected_failure_info = {
        'failed': False,
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
        'builds': {},
        'failed_steps': {},
        'failure_type': failure_type.UNKNOWN,
        'parent_mastername': None,
        'parent_buildername': None,
        'is_luci': None,
        'buildbucket_bucket': None,
        'buildbucket_id': None,
    }

    self.assertEqual(expected_failure_info, failure_info)
    self.assertFalse(should_proceed)
    mock_monitoring.assert_called_once_with(
        master_name='m',
        builder_name='b',
        failure_type='unknown',
        canonical_step_name='unknown',
        isolate_target_name='unknown',
        status='Completed',
        analysis_type='Pre-Analysis')

  @mock.patch.object(
      buildbot, 'GetBuildDataFromMilo', return_value=(200, '{"data": "data"}'))
  @mock.patch.object(
      buildbot, 'GetRecentCompletedBuilds', return_value=[125, 124])
  @mock.patch.object(buildbot, 'GetBuildResult')
  def testGetLaterBuildsWithAnySameStepFailurePassedThenFailed(
      self, mock_fn, *_):
    mock_fn.side_effect = [buildbot.SUCCESS, buildbot.FAILURE]
    self.assertEquals({},
                      ci_failure.GetLaterBuildsWithAnySameStepFailure(
                          'm', 'b', 123))

  @mock.patch.object(
      buildbot, 'GetRecentCompletedBuilds', return_value=[125, 124])
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testGetLaterBuildsWithAnySameStepFailureNotStepLevel(self, mock_fn, *_):
    build_info_1 = MockBuildInfo(result=buildbot.FAILURE, failed_steps=['b'])
    mock_fn.side_effect = [(200, build_info_1), (200, build_info_1)]
    self.assertEqual({},
                     ci_failure.GetLaterBuildsWithAnySameStepFailure(
                         'm', 'b', 123, failed_steps=['a']))

  @mock.patch.object(
      buildbot, 'GetRecentCompletedBuilds', return_value=[125, 124])
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testGetLaterBuildsWithAnySameStepFailure(self, mock_fn, *_):
    build_info_1 = MockBuildInfo(result=buildbot.FAILURE, failed_steps=['a'])
    mock_fn.side_effect = [(200, build_info_1), (200, build_info_1)]
    self.assertEqual({
        124: ['a'],
        125: ['a']
    },
                     ci_failure.GetLaterBuildsWithAnySameStepFailure(
                         'm', 'b', 123, failed_steps=['a']))

  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=[])
  @mock.patch.object(logging, 'error')
  def testGetLaterBuildsWithAnySameStepFailureNoNewerBuild(
      self, mock_logging, _):
    self.assertEqual({},
                     ci_failure.GetLaterBuildsWithAnySameStepFailure(
                         'm', 'b', 123))
    mock_logging.assert_called_once_with(
        'Failed to get latest build numbers for builder %s/%s since %d.', 'm',
        'b', 123)

  @mock.patch.object(
      build_util,
      'GetWaterfallBuildStepLog',
      return_value={'canonical_step_name': 'unsupported_step1'})
  def testStepIsSupportedForMaster(self, _):
    master_name = 'master1'
    builder_name = 'b'
    build_number = 123
    step_name = 'unsupported_step1 on master1'
    self.assertFalse(
        ci_failure._StepIsSupportedForMaster(master_name, builder_name,
                                             build_number, step_name))

  def testStepIsSupportedForMasterCompile(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'compile'
    self.assertTrue(
        ci_failure._StepIsSupportedForMaster(master_name, builder_name,
                                             build_number, step_name))

  @mock.patch.object(
      build_util,
      'GetWaterfallBuildStepLog',
      return_value={'canonical_step_name': 'step_name'})
  def testGetStepMetadataCached(self, mock_fn):
    ci_failure.GetStepMetadata('m', 'b', 200, 'step_name on a platform')
    ci_failure.GetStepMetadata('m', 'b', 200, 'step_name on a platform')
    self.assertTrue(mock_fn.call_count < 2)

  @mock.patch.object(
      ci_failure,
      'GetStepMetadata',
      return_value={'canonical_step_name': 'step_name'})
  def testGetCanonicalStep(self, _):
    self.assertEqual(
        'step_name',
        ci_failure.GetCanonicalStepName('m', 'b', 200,
                                        'step_name on a platform'))

  @mock.patch.object(
      ci_failure,
      'GetStepMetadata',
      return_value={'isolate_target_name': 'browser_tests'})
  def testGetIsolateTargetName(self, _):
    self.assertEqual(
        'browser_tests',
        ci_failure.GetIsolateTargetName(
            'm', 'b', 200, 'viz_browser_tests (with patch) on Android'))

  @mock.patch.object(ci_failure, 'GetStepMetadata', return_value=None)
  def testGetIsolateTargetNameStepMetadataIsNone(self, _):
    self.assertEqual(
        None,
        ci_failure.GetIsolateTargetName(
            'm', 'b', 200, 'viz_browser_tests (with patch) on Android'))

  @mock.patch.object(ci_failure, 'GetStepMetadata', return_value={'a': 'b'})
  def testGetIsolateTargetNameIsolateTargetNameIsMissing(self, _):
    self.assertEqual(
        None,
        ci_failure.GetIsolateTargetName(
            'm', 'b', 200, 'viz_browser_tests (with patch) on Android'))

  def testGetGoodRevision(self):
    failed_steps = {
        'a': {
            'current_failure': 124,
            'first_failure': 124,
            'last_pass': 123
        },
        'b': {
            'current_failure': 124,
            'first_failure': 124,
        },
        'c': {
            'current_failure': 124,
            'first_failure': 123,
            'last_pass': 122
        },
    }
    builds = {
        122: {
            'chromium_revision': '122_git_hash',
            'blame_list': ['122_git_hash']
        },
        123: {
            'chromium_revision': '123_git_hash',
            'blame_list': ['123_git_hash']
        },
        124: {
            'chromium_revision': '124_git_hash',
            'blame_list': ['124_git_hash']
        }
    }
    failed_steps = BaseFailedSteps.FromSerializable(failed_steps)
    builds = FailureInfoBuilds.FromSerializable(builds)
    failure_info = CompileFailureInfo(
        build_number=124, failed_steps=failed_steps, builds=builds)

    self.assertEqual('122_git_hash', ci_failure.GetGoodRevision(failure_info))

  def testGetGoodRevisionNoLastPass(self):
    failed_steps = {
        'a': {
            'current_failure': 124,
            'first_failure': 124,
        }
    }
    builds = {
        124: {
            'chromium_revision': '124_git_hash',
            'blame_list': ['124_git_hash']
        }
    }
    failed_steps = BaseFailedSteps.FromSerializable(failed_steps)
    builds = FailureInfoBuilds.FromSerializable(builds)
    failure_info = CompileFailureInfo(
        build_number=124, failed_steps=failed_steps, builds=builds)

    self.assertIsNone(ci_failure.GetGoodRevision(failure_info))
