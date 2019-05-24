# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import mock
import os

from buildbucket_proto import common_pb2
from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.rpc_pb2 import SearchBuildsResponse
from buildbucket_proto.step_pb2 import Step

from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild
from services import ci_failure
from services import git
from services import monitoring
from services import step_util
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

  @mock.patch.object(
      buildbot, 'GetBlameListForV2Build', return_value=['rev123'])
  @mock.patch.object(git, 'GetCommitPositionFromRevision', return_value=654332)
  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testStopLookingBackIfAllFailedStepsPassedInLastBuild(
      self, mock_search_builds, *_):
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
    builds = {124: {'chromium_revision': 'rev124', 'blame_list': ['rev124']}}
    failed_steps = BaseFailedSteps.FromSerializable(failed_steps)
    builds = FailureInfoBuilds.FromSerializable(builds)
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.build_id = '80000000124'
    build.completed = True
    build.put()
    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    build_123 = Build(number=123, status=common_pb2.FAILURE)
    step1 = Step(name='a', status=common_pb2.SUCCESS)
    log = step1.logs.add()
    log.name = 'stdout'
    step2 = Step(name='net_unittests', status=common_pb2.FAILURE)
    log = step2.logs.add()
    log.name = 'stdout'
    step3 = Step(name='unit_tests', status=common_pb2.FAILURE)
    log = step3.logs.add()
    log.name = 'stdout'
    build_123.steps.extend([step1, step2, step3])
    build_123.input.gitiles_commit.id = 'rev123'
    mock_search_builds.side_effect = [SearchBuildsResponse(builds=[build_123])]

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
            'chromium_revision': 'rev124',
            'blame_list': ['rev124']
        },
        123: {
            'chromium_revision': 'rev123',
            'blame_list': ['rev123']
        }
    }

    failure_info = CompileFailureInfo(failed_steps=failed_steps, builds=builds)
    failure_info = ci_failure.CheckForFirstKnownFailure(
        master_name, builder_name, build_number, failure_info)

    self.assertEqual(expected_failed_steps,
                     failure_info.failed_steps.ToSerializable())
    self.assertEqual(expected_builds, failure_info.builds.ToSerializable())

  @mock.patch.object(
      buildbot, 'GetBlameListForV2Build', side_effect=[['rev1'], ['rev0']])
  @mock.patch.object(git, 'GetCommitPositionFromRevision', return_value=654332)
  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testStopLookingBackIfFindTheFirstBuild(self, mock_search_builds, *_):
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
    builds = {'2': {'chromium_revision': 'rev2', 'blame_list': ['rev2']}}
    failed_steps = BaseFailedSteps.FromSerializable(failed_steps)
    builds = FailureInfoBuilds.FromSerializable(builds)
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.build_id = '80000000124'
    build.completed = True
    build.put()
    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    # Setup build data for builds:
    step1 = Step(name='a_tests', status=common_pb2.FAILURE)
    log = step1.logs.add()
    log.name = 'stdout'

    step2 = Step(name='unit_tests', status=common_pb2.FAILURE)
    log = step2.logs.add()
    log.name = 'stdout'

    build_1 = Build(number=1, status=common_pb2.FAILURE)
    build_1.steps.extend([step1, step2])
    build_1.input.gitiles_commit.id = 'rev1'

    build_0 = Build(number=0, status=common_pb2.FAILURE)
    build_0.steps.extend([step1, step2])
    build_0.input.gitiles_commit.id = 'rev0'

    mock_search_builds.side_effect = [
        SearchBuildsResponse(builds=[build_1]),
        SearchBuildsResponse(builds=[build_0]),
        SearchBuildsResponse(builds=[])
    ]

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
            'chromium_revision': 'rev2',
            'blame_list': ['rev2']
        },
        1: {
            'chromium_revision': 'rev1',
            'blame_list': ['rev1']
        },
        0: {
            'chromium_revision': 'rev0',
            'blame_list': ['rev0']
        },
    }
    failure_info = CompileFailureInfo(failed_steps=failed_steps, builds=builds)

    ci_failure.CheckForFirstKnownFailure(master_name, builder_name,
                                         build_number, failure_info)

    self.assertEqual(expected_failed_steps,
                     failure_info.failed_steps.ToSerializable())
    self.assertEqual(expected_builds, failure_info.builds.ToSerializable())

  @mock.patch.object(
      buildbot, 'GetBlameListForV2Build', side_effect=[['rev122'], ['rev121']])
  @mock.patch.object(git, 'GetCommitPositionFromRevision', return_value=654332)
  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testLookBackUntilGreenBuild(self, mock_search_builds, *_):
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
    builds = {123: {'chromium_revision': 'rev123', 'blame_list': ['rev123']}}
    failed_steps = BaseFailedSteps.FromSerializable(failed_steps)
    builds = FailureInfoBuilds.FromSerializable(builds)
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.build_id = '80000000123'
    build.completed = True
    build.put()

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    build_121 = Build(number=121, status=common_pb2.SUCCESS)
    build_121.input.gitiles_commit.id = 'rev121'

    build_122 = Build(number=122, status=common_pb2.FAILURE)
    step1 = Step(name='net_unittests', status=common_pb2.SUCCESS)
    log = step1.logs.add()
    log.name = 'stdout'
    step2 = Step(name='unit_tests', status=common_pb2.FAILURE)
    log = step2.logs.add()
    log.name = 'stdout'
    build_122.steps.extend([step1, step2])
    build_122.input.gitiles_commit.id = 'rev122'

    mock_search_builds.side_effect = [
        SearchBuildsResponse(builds=[build_122]),
        SearchBuildsResponse(builds=[build_121])
    ]

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
            'chromium_revision': 'rev123',
            'blame_list': ['rev123']
        },
        122: {
            'chromium_revision': 'rev122',
            'blame_list': ['rev122']
        },
        121: {
            'chromium_revision': 'rev121',
            'blame_list': ['rev121',]
        }
    }

    failure_info = CompileFailureInfo(failed_steps=failed_steps, builds=builds)
    ci_failure.CheckForFirstKnownFailure(master_name, builder_name,
                                         build_number, failure_info)
    self.assertEqual(expected_failed_steps,
                     failure_info.failed_steps.ToSerializable())
    self.assertEqual(expected_builds, failure_info.builds.ToSerializable())

  @mock.patch.object(step_util, 'StepIsSupportedForMaster', return_value=True)
  @mock.patch.object(
      buildbot, 'GetBlameListForV2Build', return_value=['rev223'])
  @mock.patch.object(git, 'GetCommitPositionFromRevision', return_value=654332)
  @mock.patch.object(buildbucket_client, 'GetV2Build')
  def testGetBuildFailureInfo(self, mock_build, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.PENDING)

    build = WfBuild.Create(master_name, builder_name, build_number)
    build.build_id = '80000000223'
    build.completed = True
    build.put()

    build_223 = Build(
        id=80000000223, number=build_number, status=common_pb2.FAILURE)
    build_223.input.gitiles_commit.id = 'rev223'
    step1 = Step(name='compile', status=common_pb2.SUCCESS)
    log = step1.logs.add()
    log.name = 'stdout'
    step2 = Step(name='abc_test', status=common_pb2.FAILURE)
    log = step2.logs.add()
    log.name = 'stdout'
    build_223.steps.extend([step1, step2])
    mock_build.return_value = build_223

    failure_info, should_proceed = ci_failure.GetBuildFailureInfo(
        master_name, builder_name, build_number)

    expected_failure_info = {
        'failed': True,
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'is_luci': None,
        'buildbucket_bucket': '',
        'buildbucket_id': 80000000223,
        'chromium_revision': 'rev223',
        'builds': {
            build_number: {
                'blame_list': ['rev223'],
                'chromium_revision': 'rev223'
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

  @mock.patch.object(build_util, 'GetBuildInfo', return_value=None)
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

  @mock.patch.object(
      buildbot, 'GetBlameListForV2Build', return_value=['rev121'])
  @mock.patch.object(git, 'GetCommitPositionFromRevision', return_value=654332)
  @mock.patch.object(buildbucket_client, 'GetV2Build')
  @mock.patch.object(monitoring, 'OnWaterfallAnalysisStateChange')
  def testGetBuildFailureInfoBuildSuccess(self, mock_monitoring, mock_build,
                                          *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.PENDING)

    build = WfBuild.Create(master_name, builder_name, build_number)
    build.build_id = '80000000223'
    build.completed = True
    build.put()

    build_121 = Build(
        id=80000000121, number=build_number, status=common_pb2.FAILURE)
    build_121.input.gitiles_commit.id = 'rev121'
    step1 = Step(name='net_unittests', status=common_pb2.SUCCESS)
    log = step1.logs.add()
    log.name = 'stdout'
    step2 = Step(name='unit_tests', status=common_pb2.SUCCESS)
    log = step2.logs.add()
    log.name = 'stdout'
    build_121.steps.extend([step1, step2])
    mock_build.return_value = build_121

    failure_info, should_proceed = ci_failure.GetBuildFailureInfo(
        master_name, builder_name, build_number)

    expected_failure_info = {
        'failed': False,
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'chromium_revision': 'rev121',
        'builds': {},
        'failed_steps': {},
        'failure_type': failure_type.UNKNOWN,
        'parent_mastername': None,
        'parent_buildername': None,
        'is_luci': None,
        'buildbucket_bucket': '',
        'buildbucket_id': 80000000121,
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
      buildbot, 'GetRecentCompletedBuilds', return_value=[125, 124])
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testGetLaterBuildsWithAnySameStepFailurePassedThenFailed(
      self, mock_build_info, _):
    mock_build_info.side_effect = [
        MockBuildInfo(result=common_pb2.FAILURE, failed_steps=['a']),
        MockBuildInfo(result=common_pb2.SUCCESS, failed_steps=None)
    ]
    self.assertEquals({},
                      ci_failure.GetLaterBuildsWithAnySameStepFailure(
                          'm', 'b', 123, failed_steps=['a']))

  @mock.patch.object(
      buildbot, 'GetRecentCompletedBuilds', return_value=[125, 124])
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testGetLaterBuildsWithAnySameStepFailureNotStepLevel(self, mock_fn, *_):
    build_info_1 = MockBuildInfo(result=common_pb2.FAILURE, failed_steps=['b'])
    mock_fn.side_effect = [build_info_1, build_info_1]
    self.assertEqual({},
                     ci_failure.GetLaterBuildsWithAnySameStepFailure(
                         'm', 'b', 123, failed_steps=['a']))

  @mock.patch.object(
      buildbot, 'GetRecentCompletedBuilds', return_value=[125, 124])
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testGetLaterBuildsWithAnySameStepFailure(self, mock_fn, *_):
    build_info_1 = MockBuildInfo(result=common_pb2.FAILURE, failed_steps=['a'])
    mock_fn.side_effect = [build_info_1, build_info_1]
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
