# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mock

from common import exceptions
from common.swarmbucket import swarmbucket
from common.waterfall import failure_type
from dto.collect_swarming_task_results_outputs import (
    CollectSwarmingTaskResultsOutputs)
from dto.start_waterfall_try_job_inputs import StartTestTryJobInputs
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import analysis_status
from libs.gitiles.change_log import Contributor
from model import analysis_approach_type
from model import result_status
from model.wf_analysis import WfAnalysis
from model.wf_failure_group import WfFailureGroup
from model.wf_swarming_task import WfSwarmingTask
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from services import build_failure_analysis
from services import try_job as try_job_service
from services.parameters import BuildKey
from services.parameters import IdentifyTestTryJobCulpritParameters
from services.parameters import RunTestTryJobParameters
from services.parameters import TestFailedSteps
from services.parameters import TestFailureInfo
from services.parameters import TestHeuristicAnalysisOutput
from services.parameters import TestHeuristicResult
from services.parameters import TestTryJobAllStepsResult
from services.parameters import TestTryJobResult
from services.test.git_test import MockedChangeLog
from services.test_failure import test_failure_analysis
from services.test_failure import test_try_job
from waterfall import suspected_cl_util
from waterfall import waterfall_config
from waterfall.test import wf_testcase


class TestTryJobTest(wf_testcase.WaterfallTestCase):

  def _MockGetChangeLog(self, revision):
    mock_change_logs = {}
    mock_change_logs['rev1'] = MockedChangeLog(
        commit_position=1,
        code_review_url='url_1',
        author=Contributor('author1', 'author1@abc.com', '2018-05-17 00:49:48'))
    mock_change_logs['rev2'] = MockedChangeLog(
        commit_position=2,
        code_review_url='url_2',
        author=Contributor('author2', 'author2@abc.com', '2018-05-17 00:49:48'))
    return mock_change_logs.get(revision)

  def setUp(self):
    super(TestTryJobTest, self).setUp()

    self.mock(CachedGitilesRepository, 'GetChangeLog', self._MockGetChangeLog)

    self.failure_info = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 223,
        'failed_steps': {},
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.TEST
    }
    self.start_try_job_params = StartTestTryJobInputs(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=223),
        build_completed=True,
        force=False,
        heuristic_result=TestHeuristicAnalysisOutput(
            failure_info=TestFailureInfo.FromSerializable(self.failure_info),
            heuristic_result=TestHeuristicResult.FromSerializable({})),
        consistent_failures=CollectSwarmingTaskResultsOutputs.FromSerializable({
            'consistent_failures': {
                's': ['t']
            }
        }))

  def testGetFailedStepsAndTests(self):
    failed_steps = TestFailedSteps.FromSerializable({
        'step_c': {},
        'step_a': {
            'tests': {
                'test_c': {},
                'test_b': {},
                'test_a': {}
            },
        },
        'step_b': {}
    })

    expected_result = [['step_a', 'test_a'], ['step_a', 'test_b'],
                       ['step_a', 'test_c'], ['step_b', None], ['step_c', None]]

    self.assertEqual(expected_result,
                     test_try_job._GetStepsAndTests(failed_steps))

  def testFailedStepsAbsent(self):
    self.assertEqual([], test_try_job._GetStepsAndTests(None))

  def testNoFailedSteps(self):
    self.assertEqual([], test_try_job._GetStepsAndTests({}))

  @mock.patch.object(logging, 'info')
  def testDoNotGroupUnknownBuildFailure(self, mock_logging):
    master_name = 'm1'
    builder_name = 'bt'
    build_number = 1

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with UNKNOWN failure.
    # Observe that the build failure is unique, but there is no new group
    # creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.UNKNOWN, None,
            None, None))
    mock_logging.assert_called_once_with(
        'Expected test failure but get unknown failure.')

  @mock.patch.object(logging, 'info')
  def testDoNotGroupInfraBuildFailure(self, mock_logging):
    master_name = 'm1'
    builder_name = 'bt'
    build_number = 2

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with INFRA failure.
    # Observe that the build failure is unique, but there is no new group
    # creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.INFRA, None,
            None, None))
    mock_logging.assert_called_once_with(
        'Expected test failure but get infra failure.')

  def testDoNotGroupTestWithNoSteps(self):
    master_name = 'm1'
    builder_name = 'bt'
    build_number = 3

    blame_list = ['a']

    failed_steps = TestFailedSteps.FromSerializable({})

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have zero failed steps.
    # Observe that the build failure is unique, but there is no new group
    # creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps, None))

  def testGroupTestsWithRelatedStepsWithHeuristicResult(self):
    master_name = 'm1'
    builder_name = 'bt'
    build_number = 4
    master_name_2 = 'm2'

    blame_list = ['a']

    failed_steps = TestFailedSteps.FromSerializable({
        'step_a': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    })

    heuristic_result = TestHeuristicResult.FromSerializable({
        'failures': [{
            'step_name': 'step1',
            'suspected_cls': [{
                'revision': 'rev1',
            }],
        }]
    })

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps, heuristic_result))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed steps.
    # Observe no new group creation.
    self.assertFalse(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps, heuristic_result))
    self.assertIsNone(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testGroupTestsWithRelatedStepsWithoutHeuristicResult(self):
    master_name = 'm1'
    builder_name = 'bt'
    build_number = 5
    master_name_2 = 'm2'

    blame_list = ['a']

    failed_steps = TestFailedSteps.FromSerializable({
        'step_a': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    })

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps, TestHeuristicResult.FromSerializable({})))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed steps.
    # Observe no new group creation.
    self.assertFalse(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps, TestHeuristicResult.FromSerializable({})))
    self.assertIsNone(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupTestsWithDisjointBlameLists(self):
    master_name = 'm1'
    builder_name = 'bt'
    build_number = 6
    master_name_2 = 'm2'

    blame_list_1 = ['a']
    blame_list_2 = ['b']
    failed_steps = TestFailedSteps.FromSerializable({
        'step_a': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    })

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number,
            failure_type.TEST, blame_list_1, failed_steps,
            TestHeuristicResult.FromSerializable({})))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number,
            failure_type.TEST, blame_list_2, failed_steps,
            TestHeuristicResult.FromSerializable({})))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupTestsWithDifferentHeuristicResults(self):
    master_name = 'm1'
    builder_name = 'bt'
    build_number = 7
    master_name_2 = 'm2'

    blame_list = ['a']
    failed_steps = TestFailedSteps.FromSerializable({
        'step_a': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    })

    heuristic_result_1 = TestHeuristicResult.FromSerializable({
        'failures': [{
            'step_name': 'step1',
            'suspected_cls': [{
                'revision': 'rev1',
            }],
        }]
    })

    heuristic_result_2 = TestHeuristicResult.FromSerializable({
        'failures': [{
            'step_name': 'step1',
            'suspected_cls': [{
                'revision': 'rev2',
            }],
        }]
    })

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps, heuristic_result_1))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps, heuristic_result_2))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupTestsWithDifferentSteps(self):
    master_name = 'm1'
    builder_name = 'bt'
    build_number = 8
    master_name_2 = 'm2'

    blame_list = ['a']

    failed_steps_1 = TestFailedSteps.FromSerializable({
        'step_a': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    })

    failed_steps_2 = TestFailedSteps.FromSerializable({
        'step_b': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    })

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number,
            failure_type.TEST, blame_list, failed_steps_1,
            TestHeuristicResult.FromSerializable({})))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number,
            failure_type.TEST, blame_list, failed_steps_2,
            TestHeuristicResult.FromSerializable({})))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  @mock.patch.object(
      try_job_service, 'NeedANewWaterfallTryJob', return_value=False)
  def testNotNeedAWaterfallTryJob(self, mock_fn):
    master_name = 'master2'
    builder_name = 'builder2'
    build_number = 223
    params = StartTestTryJobInputs(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        build_completed=True,
        force=False,
        heuristic_result=TestHeuristicAnalysisOutput.FromSerializable({}),
        consistent_failures=CollectSwarmingTaskResultsOutputs.FromSerializable(
            {}))
    need_try_job, parameters = test_try_job.GetInformationToStartATestTryJob(
        params)

    self.assertFalse(need_try_job)
    self.assertIsNone(parameters)
    mock_fn.assert_called_once_with(
        master_name, builder_name, build_number, False, build_completed=True)

  @mock.patch.object(
      try_job_service, 'NeedANewWaterfallTryJob', return_value=True)
  def testNotGetInformationToStartATestTryJobForOtherType(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {},
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.UNKNOWN
    }
    params = StartTestTryJobInputs(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        build_completed=True,
        force=False,
        heuristic_result=TestHeuristicAnalysisOutput(
            failure_info=TestFailureInfo.FromSerializable(failure_info),
            heuristic_result=TestHeuristicResult.FromSerializable({})),
        consistent_failures=CollectSwarmingTaskResultsOutputs.FromSerializable(
            {}))

    need_try_job, parameters = test_try_job.GetInformationToStartATestTryJob(
        params)

    self.assertFalse(need_try_job)
    self.assertIsNone(parameters)

  @mock.patch.object(
      try_job_service, 'NeedANewWaterfallTryJob', return_value=True)
  @mock.patch.object(test_try_job, '_NeedANewTestTryJob', return_value=False)
  def testNotNeedANewTestTryJob(self, mock_fn, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {},
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.TEST
    }

    consistent_failures = CollectSwarmingTaskResultsOutputs.FromSerializable({})
    params = StartTestTryJobInputs(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        build_completed=True,
        force=False,
        heuristic_result=TestHeuristicAnalysisOutput(
            failure_info=TestFailureInfo.FromSerializable(failure_info),
            heuristic_result=TestHeuristicResult.FromSerializable({})),
        consistent_failures=consistent_failures)

    need_try_job, parameters = test_try_job.GetInformationToStartATestTryJob(
        params)

    self.assertFalse(need_try_job)
    self.assertIsNone(parameters)
    mock_fn.assert_called_once_with(params)

  @mock.patch.object(
      try_job_service, 'NeedANewWaterfallTryJob', return_value=True)
  @mock.patch.object(
      try_job_service, 'ReviveOrCreateTryJobEntity', return_value=(False, None))
  @mock.patch.object(test_try_job, '_IsTestFailureUniqueAcrossPlatforms')
  @mock.patch.object(test_try_job, '_NeedANewTestTryJob', return_value=True)
  def testFailedToReviveOrCreateTryJob(self, mock_fn, mock_unique, mock_rc, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info_dict = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {},
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.TEST
    }

    failure_info = TestFailureInfo.FromSerializable(failure_info_dict)
    heuristic_result = TestHeuristicAnalysisOutput(
        failure_info=failure_info,
        heuristic_result=TestHeuristicResult.FromSerializable({}))
    consistent_failures = CollectSwarmingTaskResultsOutputs.FromSerializable({})
    params = StartTestTryJobInputs(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        build_completed=True,
        force=False,
        heuristic_result=heuristic_result,
        consistent_failures=consistent_failures)

    need_try_job, parameters = test_try_job.GetInformationToStartATestTryJob(
        params)

    self.assertFalse(need_try_job)
    self.assertIsNone(parameters)
    mock_fn.assert_called_once_with(params)
    mock_unique.assert_called_once_with(
        master_name, builder_name, build_number, failure_type.TEST,
        failure_info.builds['223'].blame_list, failure_info.failed_steps,
        heuristic_result.heuristic_result)
    mock_rc.assert_called_once_with(master_name, builder_name, build_number,
                                    False)

  @mock.patch.object(
      try_job_service, 'NeedANewWaterfallTryJob', return_value=True)
  @mock.patch.object(
      try_job_service,
      'ReviveOrCreateTryJobEntity',
      return_value=(True, 'try_job_key'))
  @mock.patch.object(test_try_job, '_IsTestFailureUniqueAcrossPlatforms')
  @mock.patch.object(test_try_job, '_NeedANewTestTryJob', return_value=True)
  @mock.patch.object(test_try_job, 'GetParametersToScheduleTestTryJob')
  def testNoGoodRevision(self, mock_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    failure_info_dict = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {},
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.TEST
    }
    failure_info = TestFailureInfo.FromSerializable(failure_info_dict)

    params = StartTestTryJobInputs(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        build_completed=True,
        force=False,
        heuristic_result=TestHeuristicAnalysisOutput(
            failure_info=failure_info,
            heuristic_result=TestHeuristicResult.FromSerializable({})),
        consistent_failures=CollectSwarmingTaskResultsOutputs.FromSerializable(
            {}))

    mock_parameters = RunTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        good_revision=None,
        bad_revision='rev2',
        suspected_revisions=[],
        dimensions=['os:Mac-10.9', 'cpu:x86-64', 'pool:luci.chromium.findit'],
        cache_name='cache',
        targeted_tests={},
        urlsafe_try_job_key='urlsafe_try_job_key')
    mock_fn.return_value = mock_parameters

    need_try_job, parameters = test_try_job.GetInformationToStartATestTryJob(
        params)

    self.assertFalse(need_try_job)
    self.assertIsNone(parameters)

  @mock.patch.object(
      try_job_service, 'NeedANewWaterfallTryJob', return_value=True)
  @mock.patch.object(
      try_job_service,
      'ReviveOrCreateTryJobEntity',
      return_value=(True, 'try_job_key'))
  @mock.patch.object(test_try_job, '_IsTestFailureUniqueAcrossPlatforms')
  @mock.patch.object(test_try_job, '_NeedANewTestTryJob', return_value=True)
  @mock.patch.object(test_try_job, 'GetParametersToScheduleTestTryJob')
  def testNeedANewTryJobIfTestFailureSwarming(self, mock_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info_dict = {
        'failed_steps': {
            'a': {
                'current_failure': 223,
                'first_failure': 222,
                'last_pass': 221,
                'tests': {
                    'a.PRE_t1': {
                        'current_failure': 223,
                        'first_failure': 223,
                        'last_pass': 221,
                        'base_test_name': 'a.t1'
                    },
                    'a.t2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    },
                    'a.t3': {
                        'current_failure': 223,
                        'first_failure': 223,
                        'last_pass': 222
                    }
                }
            },
            'b': {
                'current_failure': 223,
                'first_failure': 222,
                'last_pass': 221,
                'tests': {
                    'b.t1': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    },
                    'b.t2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    }
                }
            }
        },
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.TEST
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {
        'a': {
            'a.PRE_t1': 'm/b/223',
            'a.t2': 'm/b/222',
            'a.t3': 'm/b/223'
        },
        'b': {
            'b.t1': 'm/b/222',
            'b.t2': 'm/b/222'
        }
    }
    analysis.put()

    failure_info = TestFailureInfo.FromSerializable(failure_info_dict)
    heuristic_result = TestHeuristicAnalysisOutput(
        failure_info=failure_info,
        heuristic_result=TestHeuristicResult.FromSerializable({}))
    consistent_failures = CollectSwarmingTaskResultsOutputs.FromSerializable({})
    params = StartTestTryJobInputs(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        build_completed=True,
        force=False,
        heuristic_result=heuristic_result,
        consistent_failures=consistent_failures)

    mock_parameters = RunTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        good_revision='rev1',
        bad_revision='rev2',
        suspected_revisions=[],
        dimensions=['os:Mac-10.9', 'cpu:x86-64', 'pool:luci.chromium.findit'],
        cache_name='cache',
        targeted_tests={},
        urlsafe_try_job_key='urlsafe_try_job_key')
    mock_fn.return_value = mock_parameters

    need_try_job, parameters = test_try_job.GetInformationToStartATestTryJob(
        params)

    self.assertTrue(need_try_job)
    self.assertEqual(mock_parameters, parameters)
    mock_fn.assert_called_once_with(
        master_name, builder_name, build_number, failure_info,
        heuristic_result.heuristic_result, 'try_job_key', consistent_failures)

  def testGetLastPassTestNoLastPass(self):
    failed_steps = TestFailedSteps.FromSerializable({
        'a': {
            'first_failure': 1,
            'last_pass': 0,
            'tests': {
                'test1': {
                    'first_failure': 1
                }
            }
        }
    })
    self.assertIsNone(test_try_job._GetLastPassTest(1, failed_steps))

  def testGetLastPassTest(self):
    failed_steps = TestFailedSteps.FromSerializable({
        'a': {
            'first_failure': 1,
            'last_pass': 0,
            'tests': {
                'test1': {
                    'first_failure': 1,
                    'last_pass': 0
                }
            }
        }
    })
    self.assertEqual(0, test_try_job._GetLastPassTest(1, failed_steps))

  def testGetGoodRevisionTest(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    failure_info = TestFailureInfo.FromSerializable({
        'failed_steps': {
            'a': {
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'test1': {
                        'first_failure': 1,
                        'last_pass': 0
                    }
                }
            }
        },
        'builds': {
            '0': {
                'chromium_revision': 'rev1'
            },
            '1': {
                'chromium_revision': 'rev2'
            }
        }
    })
    self.assertEqual(
        'rev1',
        test_try_job._GetGoodRevisionTest(master_name, builder_name,
                                          build_number, failure_info))

  def testNotGetGoodRevisionTest(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = TestFailureInfo.FromSerializable({
        'failed_steps': {
            'a': {
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'test1': {
                        'first_failure': 1,
                        'last_pass': 0
                    }
                }
            }
        },
        'builds': {
            '0': {
                'chromium_revision': 'rev1'
            },
            '1': {
                'chromium_revision': 'rev2'
            }
        }
    })
    self.assertIsNone(
        test_try_job._GetGoodRevisionTest(master_name, builder_name,
                                          build_number, failure_info))

  @mock.patch.object(test_try_job, 'GetReliableTests', return_value={})
  @mock.patch('services.swarmbot_util.GetCacheName', return_value='cache')
  @mock.patch.object(swarmbucket, 'GetDimensionsForBuilder')
  def testGetParametersToScheduleTestTryJob(self, mock_dimensions, *_):
    mock_dimensions.return_value = ['os:Mac-10.9', 'cpu:x86-64']
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    failure_info = TestFailureInfo.FromSerializable({
        'failed_steps': {
            'a': {
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'test1': {
                        'first_failure': 1,
                        'last_pass': 0
                    }
                }
            }
        },
        'builds': {
            '0': {
                'chromium_revision': 'rev1'
            },
            '1': {
                'chromium_revision': 'rev2'
            }
        }
    })
    consistent_failures_dict = {'consistent_failures': {'a': ['test1']}}
    consistent_failures = CollectSwarmingTaskResultsOutputs.FromSerializable(
        consistent_failures_dict)

    expected_parameters = RunTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        good_revision='rev1',
        bad_revision='rev2',
        suspected_revisions=[],
        dimensions=['os:Mac-10.9', 'cpu:x86-64', 'pool:luci.chromium.findit'],
        cache_name='cache',
        targeted_tests={'a': ['test1']},
        urlsafe_try_job_key='urlsafe_try_job_key')
    self.assertEqual(
        expected_parameters,
        test_try_job.GetParametersToScheduleTestTryJob(
            master_name, builder_name, build_number, failure_info, None,
            'urlsafe_try_job_key', consistent_failures))

  def testGetSwarmingTasksResult(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_type = failure_type.TEST
    failure_info = {
        'parent_mastername': None,
        'parent_buildername': None,
        'failure_type': try_job_type,
        'builds': {
            '0': {
                'blame_list': ['r0', 'r1'],
                'chromium_revision': 'r1'
            },
            '1': {
                'blame_list': ['r2'],
                'chromium_revision': 'r2'
            }
        },
        'failed_steps': {
            'a on platform': {
                'first_failure': 1,
                'tests': {
                    'test1': {
                        'first_failure': 1
                    },
                    'test2': {
                        'first_failure': 1
                    }
                }
            },
            'b': {
                'first_failure': 1,
                'tests': {
                    'b_test1': {
                        'first_failure': 1
                    }
                }
            },
            'c': {
                'first_failure': 0,
                'tests': {
                    'b_test1': {
                        'first_failure': 0
                    }
                }
            }
        }
    }

    task1 = WfSwarmingTask.Create(master_name, builder_name, build_number,
                                  'a on platform')
    task1.tests_statuses = {'test1': {'SUCCESS': 6}, 'test2': {'FAILURE': 6}}
    task1.canonical_step_name = 'a'
    task1.put()

    task2 = WfSwarmingTask.Create(master_name, builder_name, build_number, 'b')
    task2.tests_statuses = {'b_test1': {'SUCCESS': 6}}
    task2.put()

    task_results = test_try_job.GetReliableTests(master_name, builder_name,
                                                 build_number, failure_info)

    expected_results = {'a': ['test2']}

    self.assertEqual(expected_results, task_results)

  def testGetReliableTestsNoTask(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_type = failure_type.TEST
    failure_info = {
        'parent_mastername': None,
        'parent_buildername': None,
        'failure_type': try_job_type,
        'builds': {
            '0': {
                'blame_list': ['r0', 'r1'],
                'chromium_revision': 'r1'
            },
            '1': {
                'blame_list': ['r2'],
                'chromium_revision': 'r2'
            }
        },
        'failed_steps': {
            'a on platform': {
                'first_failure': 1,
                'tests': {
                    'test1': {
                        'first_failure': 1
                    },
                    'test2': {
                        'first_failure': 1
                    }
                }
            },
            'b': {
                'first_failure': 1,
                'tests': {
                    'b_test1': {
                        'first_failure': 1
                    }
                }
            },
            'c': {
                'first_failure': 0,
                'tests': {
                    'b_test1': {
                        'first_failure': 0
                    }
                }
            }
        }
    }
    self.assertEqual({},
                     test_try_job.GetReliableTests(master_name, builder_name,
                                                   build_number, failure_info))

  def testGetBuildPropertiesForTestFailure(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1

    pipeline_input = RunTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        good_revision='1',
        bad_revision='2',
        suspected_revisions=[])

    expected_properties = {
        'recipe':
            'findit/chromium/test',
        'good_revision':
            '1',
        'bad_revision':
            '2',
        'target_mastername':
            master_name,
        'target_testername':
            'b',
        'suspected_revisions': [],
        'referenced_build_url': ('https://ci.chromium.org/buildbot/%s/%s/%s') %
                                (master_name, builder_name, build_number)
    }
    properties = test_try_job.GetBuildProperties(pipeline_input)

    self.assertEqual(properties, expected_properties)

  def testGetResultAnalysisStatusAllFlake(self):
    self.assertEqual(result_status.FLAKY,
                     test_try_job._GetResultAnalysisStatus(None, None, True))

  @mock.patch.object(
      try_job_service,
      'GetResultAnalysisStatus',
      return_value=result_status.FOUND_UNTRIAGED)
  def testGetResultAnalysisStatus(self, _):
    self.assertEqual(result_status.FOUND_UNTRIAGED,
                     test_try_job._GetResultAnalysisStatus(None, None))

  def testGetTestFailureCausedByCL(self):
    self.assertIsNone(test_try_job._GetTestFailureCausedByCL(None))

  def testGetTestFailureCausedByCLPassed(self):
    result = {
        'a_test': {
            'status': 'passed',
            'valid': True,
        },
        'b_test': {
            'status': 'failed',
            'valid': True,
            'failures': ['b_test1']
        }
    }

    expected_failures = {'b_test': ['b_test1']}

    self.assertEqual(
        expected_failures,
        test_try_job._GetTestFailureCausedByCL(
            TestTryJobAllStepsResult.FromSerializable(result)))

  def testGetSuspectedCLsForTestTryJobAndHeuristicResultsSame(self):
    suspected_cl = {
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'repo_name': 'chromium'
    }

    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.suspected_cls = [suspected_cl]
    analysis.put()

    try_job_suspected_cls = {'rev1': suspected_cl}

    updated_cls = test_try_job._GetUpdatedSuspectedCLs(analysis, None,
                                                       try_job_suspected_cls)

    self.assertEqual(updated_cls, [suspected_cl])

  def testGetSuspectedCLsForTestTryJob(self):
    suspected_cl1 = {
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'repo_name': 'chromium'
    }
    suspected_cl2 = {
        'revision': 'rev2',
        'commit_position': 2,
        'url': 'url_2',
        'repo_name': 'chromium'
    }
    suspected_cl3 = {
        'revision': 'rev3',
        'commit_position': 3,
        'url': 'url_3',
        'repo_name': 'chromium'
    }

    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.suspected_cls = [suspected_cl3]
    analysis.put()

    try_job_suspected_cls = {'rev1': suspected_cl1, 'rev2': suspected_cl2}

    result = {
        'report': {
            'result': {
                'rev1': {
                    'step1': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['test1']
                    }
                },
                'rev2': {
                    'step1': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['test2']
                    }
                }
            }
        }
    }

    expected_cls = [
        suspected_cl3, {
            'revision': 'rev1',
            'commit_position': 1,
            'url': 'url_1',
            'repo_name': 'chromium',
            'failures': {
                'step1': ['test1']
            },
            'top_score': None
        }, {
            'revision': 'rev2',
            'commit_position': 2,
            'url': 'url_2',
            'repo_name': 'chromium',
            'failures': {
                'step1': ['test2']
            },
            'top_score': None
        }
    ]

    cl_result = test_try_job._GetUpdatedSuspectedCLs(
        analysis, TestTryJobResult.FromSerializable(result),
        try_job_suspected_cls)
    self.assertEqual(cl_result, expected_cls)

  def testGetSuspectedCLsForTestTryJobWithHeuristicResult(self):
    suspected_cl = {
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'repo_name': 'chromium',
        'failures': {
            'step1': ['test1']
        },
        'top_score': 2
    }

    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.suspected_cls = [suspected_cl]
    analysis.put()

    result = {
        'report': {
            'result': {
                'rev1': {
                    'step1': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['test1']
                    }
                }
            }
        }
    }

    self.assertEqual(
        test_try_job._GetUpdatedSuspectedCLs(analysis, result, {}),
        [suspected_cl])

  def testFindCulpritForEachTestFailureRevisionNotRun(self):
    result = {'report': {'result': {'rev2': {'a': {'status': 'passed'}}}}}

    culprit_map, failed_revisions = test_try_job.FindCulpritForEachTestFailure(
        TestTryJobResult.FromSerializable(result))
    self.assertEqual(culprit_map, {})
    self.assertEqual(failed_revisions, [])

  def testFindCulpritForEachTestFailureCulpritsReturned(self):
    result = {'report': {'culprits': {'a_tests': {'Test1': 'rev1'}}}}

    culprit_map, failed_revisions = test_try_job.FindCulpritForEachTestFailure(
        TestTryJobResult.FromSerializable(result))

    expected_culprit_map = {
        'a_tests': {
            'tests': {
                'Test1': {
                    'revision': 'rev1'
                }
            }
        }
    }

    self.assertEqual(culprit_map, expected_culprit_map)
    self.assertEqual(failed_revisions, ['rev1'])

  def testUpdateTryJobResult(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    WfTryJob.Create(master_name, builder_name, build_number).put()
    parameters = IdentifyTestTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=None)
    test_try_job.UpdateTryJobResult(parameters, None)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(try_job.status, analysis_status.COMPLETED)

  def testGetUpdatedAnalysisResultNoAnalysis(self):
    self.assertEqual(({}, False),
                     test_try_job._GetUpdatedAnalysisResult(None, {}))

  @mock.patch.object(test_failure_analysis, 'UpdateAnalysisResultWithFlakeInfo')
  def testGetUpdatedAnalysisResult(self, mock_update):
    result = {'failures': [{'step_name': 'step1'}]}
    mock_update.return_value = (result, True)

    analysis = WfAnalysis.Create('m', 'b', 123)
    analysis.result = result
    analysis.put()

    self.assertEqual((result, True),
                     test_try_job._GetUpdatedAnalysisResult(analysis, {}))

  def testUpdateCulpritMapWithCulpritInfo(self):
    culprit_map = {'a_tests': {'tests': {'Test1': {'revision': 'rev1'}}}}
    culprits = {'rev1': {'revision': 'rev1', 'repo_name': 'chromium'}}

    expected_culprit_map = {
        'a_tests': {
            'tests': {
                'Test1': {
                    'revision': 'rev1',
                    'repo_name': 'chromium'
                }
            }
        }
    }

    test_try_job.UpdateCulpritMapWithCulpritInfo(culprit_map, culprits)
    self.assertEqual(expected_culprit_map, culprit_map)

  def testGetCulpritDataForTest(self):
    culprit_map = {
        'a_tests': {
            'tests': {
                'Test1': {
                    'revision': 'rev1',
                    'repo_name': 'chromium'
                }
            }
        }
    }

    expected_culprit_data = {'a_tests': {'Test1': 'rev1'}}

    self.assertEqual(expected_culprit_data,
                     test_try_job.GetCulpritDataForTest(culprit_map))

  @mock.patch.object(test_try_job, '_GetUpdatedAnalysisResult')
  def testUpdateWfAnalysisWithTryJobResultNoUpdate(self, mock_fn):
    test_try_job.UpdateWfAnalysisWithTryJobResult('m', 'n', 1, None, None, None)
    self.assertFalse(mock_fn.called)

  @mock.patch.object(
      test_try_job, '_GetUpdatedAnalysisResult', return_value=({}, True))
  @mock.patch.object(
      test_try_job,
      '_GetResultAnalysisStatus',
      return_value=result_status.FOUND_UNTRIAGED)
  @mock.patch.object(test_try_job, '_GetUpdatedSuspectedCLs', return_value=[])
  def testUpdateWfAnalysisWithTryJobResult(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    test_try_job.UpdateWfAnalysisWithTryJobResult(master_name, builder_name,
                                                  build_number,
                                                  TestTryJobResult(), ['rev1'],
                                                  {})
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual(analysis.result_status, result_status.FOUND_UNTRIAGED)

  @mock.patch.object(suspected_cl_util, 'UpdateSuspectedCL')
  def testUpdateSuspectedCLsNoCulprit(self, mock_fn):
    test_try_job.UpdateSuspectedCLs('m', 'b', 1, None, None)
    self.assertFalse(mock_fn.called)

  @mock.patch.object(suspected_cl_util, 'UpdateSuspectedCL')
  def testUpdateSuspectedCLs(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    result = {
        'report': {
            'result': {
                'rev': {
                    'a_test': {
                        'status': 'passed',
                        'valid': True,
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                }
            }
        }
    }
    culprits = {'rev': {'revision': 'rev', 'repo_name': 'chromium'}}
    test_try_job.UpdateSuspectedCLs(master_name, builder_name, build_number,
                                    culprits,
                                    TestTryJobResult.FromSerializable(result))
    mock_fn.assert_called_once_with(
        'chromium', 'rev', None, analysis_approach_type.TRY_JOB, master_name,
        builder_name, build_number, failure_type.TEST, {'b_test': ['b_test1']},
        None)

  def _CreateEntities(self, master_name, builder_name, build_number, try_job_id,
                      try_job_status, test_results):
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = try_job_status
    try_job.test_results = test_results
    try_job.put()

    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

  def testIdentifyCulpritForTestTryJobSuccess(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    test_result = {
        'report': {
            'last_checked_out_revision': 'rev',
            'metadata': {},
            'previously_cached_revision': 'rev',
            'previously_checked_out_revision': 'rev',
            'result': {
                'rev0': {
                    'a_test': {
                        'status': 'passed',
                        'valid': True,
                        'step_metadata': {
                            'dimensions': {
                                'gpu': 'none',
                                'os': 'Windows-7-SP1',
                                'cpu': 'x86-64',
                                'pool': 'Chrome'
                            },
                            'waterfall_buildername': 'b',
                            'waterfall_mastername': 'm',
                            'full_step_name': 'a_test',
                            'canonical_step_name': 'a_test',
                            'patched': False,
                            'swarm_task_ids': ['id1'],
                        },
                        'pass_fail_counts': {}
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1'],
                        'step_metadata': {
                            'dimensions': {
                                'gpu': 'none',
                                'os': 'Windows-7-SP1',
                                'cpu': 'x86-64',
                                'pool': 'Chrome'
                            },
                            'waterfall_buildername': 'b',
                            'waterfall_mastername': 'm',
                            'full_step_name': 'b_test',
                            'canonical_step_name': 'b_test',
                            'patched': False,
                            'swarm_task_ids': ['id2'],
                        },
                        'pass_fail_counts': {
                            'b_test1': {
                                'pass_count': 0,
                                'fail_count': 20
                            },
                        }
                    }
                },
                'rev1': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1'],
                        'step_metadata': {
                            'dimensions': {
                                'gpu': 'none',
                                'os': 'Windows-7-SP1',
                                'cpu': 'x86-64',
                                'pool': 'Chrome'
                            },
                            'waterfall_buildername': 'b',
                            'waterfall_mastername': 'm',
                            'full_step_name': 'a_test',
                            'canonical_step_name': 'a_test',
                            'patched': False,
                            'swarm_task_ids': ['id3'],
                        },
                        'pass_fail_counts': {
                            'a_test1': {
                                'pass_count': 0,
                                'fail_count': 20
                            },
                        }
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1'],
                        'step_metadata': {
                            'dimensions': {
                                'gpu': 'none',
                                'os': 'Windows-7-SP1',
                                'cpu': 'x86-64',
                                'pool': 'Chrome'
                            },
                            'waterfall_buildername': 'b',
                            'waterfall_mastername': 'm',
                            'full_step_name': 'b_test',
                            'canonical_step_name': 'b_test',
                            'patched': False,
                            'swarm_task_ids': ['id4'],
                        },
                        'pass_fail_counts': {
                            'b_test1': {
                                'pass_count': 0,
                                'fail_count': 20
                            },
                        }
                    }
                },
                'rev2': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1', 'a_test2'],
                        'step_metadata': {
                            'dimensions': {
                                'gpu': 'none',
                                'os': 'Windows-7-SP1',
                                'cpu': 'x86-64',
                                'pool': 'Chrome'
                            },
                            'waterfall_buildername': 'b',
                            'waterfall_mastername': 'm',
                            'full_step_name': 'a_test',
                            'canonical_step_name': 'a_test',
                            'patched': False,
                            'swarm_task_ids': ['id5'],
                        },
                        'pass_fail_counts': {
                            'a_test1': {
                                'pass_count': 0,
                                'fail_count': 20
                            },
                            'a_test2': {
                                'pass_count': 0,
                                'fail_count': 20
                            },
                        }
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1'],
                        'step_metadata': {
                            'dimensions': {
                                'gpu': 'none',
                                'os': 'Windows-7-SP1',
                                'cpu': 'x86-64',
                                'pool': 'Chrome'
                            },
                            'waterfall_buildername': 'b',
                            'waterfall_mastername': 'm',
                            'full_step_name': 'b_test',
                            'canonical_step_name': 'b_test',
                            'patched': False,
                            'swarm_task_ids': ['id6'],
                        },
                        'pass_fail_counts': {
                            'b_test1': {
                                'pass_count': 0,
                                'fail_count': 20
                            },
                        }
                    }
                }
            },
            'culprits': {
                'a_test': {
                    'a_test1': 'rev1',
                    'a_test2': 'rev2'
                },
            },
            'flakes': {
                'b_test': ['b_test1']
            }
        },
        'url': 'url',
        'try_job_id': try_job_id
    }

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING,
        test_results=[test_result])

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    expected_culprit_info_1 = {
        'revision': 'rev1',
        'repo_name': 'chromium',
        'commit_position': 1,
        'url': 'url_1',
        'author': 'author1@abc.com'
    }
    expected_culprit_info_2 = {
        'revision': 'rev2',
        'repo_name': 'chromium',
        'commit_position': 2,
        'url': 'url_2',
        'author': 'author2@abc.com',
    }
    expected_test_result = {
        'report': {
            'last_checked_out_revision': 'rev',
            'metadata': {},
            'previously_cached_revision': 'rev',
            'previously_checked_out_revision': 'rev',
            'result': {
                'rev0': {
                    'a_test': {
                        'status': 'passed',
                        'valid': True,
                        'failures': None,
                        'step_metadata': {
                            'dimensions': {
                                'gpu': 'none',
                                'os': 'Windows-7-SP1',
                                'cpu': 'x86-64',
                                'pool': 'Chrome'
                            },
                            'waterfall_buildername': 'b',
                            'waterfall_mastername': 'm',
                            'full_step_name': 'a_test',
                            'canonical_step_name': 'a_test',
                            'patched': False,
                            'swarm_task_ids': ['id1'],
                        },
                        'pass_fail_counts': {}
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1'],
                        'step_metadata': {
                            'dimensions': {
                                'gpu': 'none',
                                'os': 'Windows-7-SP1',
                                'cpu': 'x86-64',
                                'pool': 'Chrome'
                            },
                            'waterfall_buildername': 'b',
                            'waterfall_mastername': 'm',
                            'full_step_name': 'b_test',
                            'canonical_step_name': 'b_test',
                            'patched': False,
                            'swarm_task_ids': ['id2'],
                        },
                        'pass_fail_counts': {
                            'b_test1': {
                                'pass_count': 0,
                                'fail_count': 20
                            },
                        }
                    }
                },
                'rev1': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1'],
                        'step_metadata': {
                            'dimensions': {
                                'gpu': 'none',
                                'os': 'Windows-7-SP1',
                                'cpu': 'x86-64',
                                'pool': 'Chrome'
                            },
                            'waterfall_buildername': 'b',
                            'waterfall_mastername': 'm',
                            'full_step_name': 'a_test',
                            'canonical_step_name': 'a_test',
                            'patched': False,
                            'swarm_task_ids': ['id3'],
                        },
                        'pass_fail_counts': {
                            'a_test1': {
                                'pass_count': 0,
                                'fail_count': 20
                            },
                        }
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1'],
                        'step_metadata': {
                            'dimensions': {
                                'gpu': 'none',
                                'os': 'Windows-7-SP1',
                                'cpu': 'x86-64',
                                'pool': 'Chrome'
                            },
                            'waterfall_buildername': 'b',
                            'waterfall_mastername': 'm',
                            'full_step_name': 'b_test',
                            'canonical_step_name': 'b_test',
                            'patched': False,
                            'swarm_task_ids': ['id4'],
                        },
                        'pass_fail_counts': {
                            'b_test1': {
                                'pass_count': 0,
                                'fail_count': 20
                            },
                        }
                    }
                },
                'rev2': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1', 'a_test2'],
                        'step_metadata': {
                            'dimensions': {
                                'gpu': 'none',
                                'os': 'Windows-7-SP1',
                                'cpu': 'x86-64',
                                'pool': 'Chrome'
                            },
                            'waterfall_buildername': 'b',
                            'waterfall_mastername': 'm',
                            'full_step_name': 'a_test',
                            'canonical_step_name': 'a_test',
                            'patched': False,
                            'swarm_task_ids': ['id5'],
                        },
                        'pass_fail_counts': {
                            'a_test1': {
                                'pass_count': 0,
                                'fail_count': 20
                            },
                            'a_test2': {
                                'pass_count': 0,
                                'fail_count': 20
                            },
                        }
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1'],
                        'step_metadata': {
                            'dimensions': {
                                'gpu': 'none',
                                'os': 'Windows-7-SP1',
                                'cpu': 'x86-64',
                                'pool': 'Chrome'
                            },
                            'waterfall_buildername': 'b',
                            'waterfall_mastername': 'm',
                            'full_step_name': 'b_test',
                            'canonical_step_name': 'b_test',
                            'patched': False,
                            'swarm_task_ids': ['id6'],
                        },
                        'pass_fail_counts': {
                            'b_test1': {
                                'pass_count': 0,
                                'fail_count': 20
                            },
                        }
                    }
                }
            },
            'culprits': {
                'a_test': {
                    'a_test1': 'rev1',
                    'a_test2': 'rev2'
                },
            },
            'flakes': {
                'b_test': ['b_test1']
            }
        },
        'url': 'url',
        'try_job_id': try_job_id,
        'culprit': {
            'a_test': {
                'tests': {
                    'a_test1': expected_culprit_info_1,
                    'a_test2': expected_culprit_info_2
                }
            }
        }
    }

    parameters = IdentifyTestTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=TestTryJobResult.FromSerializable(test_result))
    culprits, _heuristic_cls, failure_to_culprit_map = (
        test_try_job.IdentifyTestTryJobCulprits(parameters))

    expected_culprits = {
        'rev1': expected_culprit_info_1,
        'rev2': expected_culprit_info_2
    }

    expected_culprit_data = {
        'a_test': {
            'a_test1': 'rev1',
            'a_test2': 'rev2',
        }
    }

    self.assertEqual(culprits, expected_culprits)
    self.assertEqual(expected_culprit_data,
                     failure_to_culprit_map.ToSerializable())

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_test_result, try_job.test_results[-1])
    self.assertEqual(analysis_status.COMPLETED, try_job.status)
    try_job_data = WfTryJobData.Get(try_job_id)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    expected_cls = [{
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'author': 'author1@abc.com',
        'repo_name': 'chromium',
        'failures': {
            'a_test': ['a_test1'],
            'b_test': ['b_test1'],
        },
        'top_score': None
    }, {
        'revision': 'rev2',
        'commit_position': 2,
        'url': 'url_2',
        'author': 'author2@abc.com',
        'repo_name': 'chromium',
        'failures': {
            'a_test': ['a_test1', 'a_test2'],
            'b_test': ['b_test1'],
        },
        'top_score': None
    }]
    self.assertEqual(expected_culprit_data, try_job_data.culprits)
    self.assertEqual(analysis.result_status, result_status.FOUND_UNTRIAGED)
    self.assertEqual(analysis.suspected_cls, expected_cls)

  @mock.patch.object(
      test_try_job, 'FindCulpritForEachTestFailure', return_value=({}, []))
  @mock.patch.object(test_try_job, 'UpdateTryJobResult')
  @mock.patch.object(
      build_failure_analysis, 'GetHeuristicSuspectedCLs', return_value=[])
  @mock.patch.object(test_try_job, 'UpdateWfAnalysisWithTryJobResult')
  @mock.patch.object(test_try_job, 'UpdateSuspectedCLs')
  def testIdentifyTestTryJobCulpritsNoCulprit(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    test_result = {
        'report': {
            'result': {
                'rev0': {
                    'a_test': {
                        'status': 'passed',
                        'valid': True,
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                },
                'rev1': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                },
                'rev2': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1', 'a_test2']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                }
            },
            'culprits': {
                'a_test': {
                    'a_test1': 'rev1',
                    'a_test2': 'rev2'
                },
            },
            'flakes': {
                'b_test': ['b_test1']
            }
        },
        'url': 'url',
        'try_job_id': try_job_id
    }

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING,
        test_results=[test_result])

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    parameters = IdentifyTestTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=TestTryJobResult.FromSerializable(test_result))
    culprits, _, _ = test_try_job.IdentifyTestTryJobCulprits(parameters)
    self.assertEqual({}, culprits)

  def testIdentifyTestTryJobCulpritsNoResult(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    test_result = None

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING,
        test_results=[test_result])

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    parameters = IdentifyTestTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=None)
    culprits, _, _ = test_try_job.IdentifyTestTryJobCulprits(parameters)
    self.assertIsNone(culprits)

  @mock.patch.object(test_try_job, 'GetBuildProperties', return_value={})
  @mock.patch.object(try_job_service, 'TriggerTryJob', return_value=('1', None))
  def testSuccessfullyScheduleNewTryJobForTest(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    good_revision = 'rev1'
    bad_revision = 'rev2'
    targeted_tests = {'a': ['test1', 'test2']}
    build_id = '1'
    WfTryJob.Create(master_name, builder_name, build_number).put()

    parameters = RunTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        bad_revision=bad_revision,
        good_revision=good_revision,
        suspected_revisions=[],
        targeted_tests=targeted_tests,
        dimensions=[],
        cache_name=None)

    try_job_id = test_try_job.ScheduleTestTryJob(parameters, 'pipeline')

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(try_job_id, build_id)
    self.assertEqual(try_job.test_results[-1]['try_job_id'], build_id)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNotNone(try_job_data)
    self.assertEqual(try_job_data.build_number, build_number)
    self.assertEqual(
        try_job_data.try_job_type,
        failure_type.GetDescriptionForFailureType(failure_type.TEST))
    self.assertFalse(try_job_data.has_compile_targets)
    self.assertFalse(try_job_data.has_heuristic_results)

  class MockedError(object):

    def __init__(self, message, reason):
      self.message = message
      self.reason = reason

  @mock.patch.object(test_try_job, 'GetBuildProperties', return_value={})
  @mock.patch.object(
      try_job_service,
      'TriggerTryJob',
      return_value=(None, MockedError('message', 'reason')))
  def testScheduleTestTryJobRaise(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    good_revision = 'rev1'
    bad_revision = 'rev2'
    targeted_tests = {'a': ['test1', 'test2']}

    parameters = RunTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        bad_revision=bad_revision,
        good_revision=good_revision,
        suspected_revisions=[],
        targeted_tests=targeted_tests,
        dimensions=[],
        cache_name=None)

    with self.assertRaises(exceptions.RetryException):
      test_try_job.ScheduleTestTryJob(parameters, 'pipeline')

  def testHasBuildKeyForBuildInfoInFailureResultMap(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 225
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {'a': {'a.t2': 'm/b/222', 'a.t3': 'm/b/225'}}
    analysis.put()
    self.assertTrue(
        test_try_job._HasBuildKeyForBuildInfoInFailureResultMap(
            master_name, builder_name, build_number))

  def testDoesntHaveBuildKeyForBuildInfoInFailureResultMap(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 225
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {'a': {'a.t2': 'm/b/222',}}
    analysis.put()
    self.assertFalse(
        test_try_job._HasBuildKeyForBuildInfoInFailureResultMap(
            master_name, builder_name, build_number))

  @mock.patch.object(
      try_job_service, 'NeedANewWaterfallTryJob', return_value=True)
  @mock.patch.object(
      waterfall_config, 'ShouldSkipTestTryJobs', return_value=True)
  def testNotNeedANewTestTryJobShouldSkip(self, *_):
    self.assertFalse(
        test_try_job._NeedANewTestTryJob(self.start_try_job_params))

  @mock.patch.object(
      try_job_service, 'NeedANewWaterfallTryJob', return_value=True)
  @mock.patch.object(
      waterfall_config, 'ShouldSkipTestTryJobs', return_value=False)
  def testNotNeedANewTestTryJobNoConsistentFailure(self, *_):
    params = StartTestTryJobInputs(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=223),
        build_completed=True,
        force=False,
        heuristic_result=TestHeuristicAnalysisOutput(
            failure_info=TestFailureInfo.FromSerializable(self.failure_info),
            heuristic_result=TestHeuristicResult.FromSerializable({})),
        consistent_failures=CollectSwarmingTaskResultsOutputs.FromSerializable(
            {}))
    self.assertFalse(test_try_job._NeedANewTestTryJob(params))

  @mock.patch.object(
      try_job_service, 'NeedANewWaterfallTryJob', return_value=True)
  def testNotNeedANewTestTryJobIfNoFailureInfo(self, _):
    params = StartTestTryJobInputs(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=223),
        build_completed=True,
        force=False,
        heuristic_result=TestHeuristicAnalysisOutput(
            failure_info=TestFailureInfo.FromSerializable({}),
            heuristic_result=TestHeuristicResult.FromSerializable({})),
        consistent_failures=CollectSwarmingTaskResultsOutputs.FromSerializable(
            {}))
    self.assertFalse(test_try_job._NeedANewTestTryJob(params))

  @mock.patch.object(
      try_job_service, 'NeedANewWaterfallTryJob', return_value=True)
  @mock.patch.object(
      test_try_job,
      '_HasBuildKeyForBuildInfoInFailureResultMap',
      return_value=True)
  @mock.patch.object(
      waterfall_config, 'ShouldSkipTestTryJobs', return_value=False)
  def testNeedANewTestTryJobNoConsistentFailure(self, *_):
    self.assertTrue(test_try_job._NeedANewTestTryJob(self.start_try_job_params))

  @mock.patch.object(test_failure_analysis,
                     'RecordTestFailureAnalysisStateChange')
  @mock.patch.object(
      try_job_service,
      'OnTryJobStateChanged',
      return_value=({}, analysis_status.COMPLETED))
  def testOnTryJobStateChanged(self, mock_fn, mock_mon):
    try_job_id = '1'
    build_json = {}
    parameters = RunTestTryJobParameters(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=1),
        good_revision='rev1',
        bad_revision='rev2',
        suspected_revisions=[],
        dimensions=['os:Mac-10.9', 'cpu:x86-64', 'pool:luci.chromium.findit'],
        cache_name='cache',
        targeted_tests={'a': ['test1']},
        urlsafe_try_job_key='urlsafe_try_job_key')

    self.assertEqual(
        TestTryJobResult.FromSerializable({}),
        test_try_job.OnTryJobStateChanged(try_job_id, build_json, parameters))
    mock_fn.assert_called_once_with(try_job_id, failure_type.TEST, build_json)
    mock_mon.assert_called_once_with('m', 'b', 1, 'a',
                                     analysis_status.COMPLETED,
                                     analysis_approach_type.TRY_JOB)

  @mock.patch.object(test_failure_analysis,
                     'RecordTestFailureAnalysisStateChange')
  @mock.patch.object(
      try_job_service,
      'OnTryJobStateChanged',
      return_value=(None, analysis_status.RUNNING))
  def testOnTryJobStateChangedNoneResult(self, mock_fn, mock_mon):
    try_job_id = '1'
    build_json = {}
    parameters = RunTestTryJobParameters(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=1),
        good_revision='rev1',
        bad_revision='rev2',
        suspected_revisions=[],
        dimensions=['os:Mac-10.9', 'cpu:x86-64', 'pool:luci.chromium.findit'],
        cache_name='cache',
        targeted_tests={'a': ['test1']},
        urlsafe_try_job_key='urlsafe_try_job_key')
    self.assertIsNone(
        test_try_job.OnTryJobStateChanged(try_job_id, build_json, parameters))
    mock_fn.assert_called_once_with(try_job_id, failure_type.TEST, build_json)
    self.assertFalse(mock_mon.called)

  @mock.patch.object(try_job_service, 'OnTryJobTimeout')
  @mock.patch.object(test_failure_analysis,
                     'RecordTestFailureAnalysisStateChange')
  def testOnTryJobTimeout(self, mock_mon, _):
    parameters = RunTestTryJobParameters(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=1),
        good_revision='rev1',
        bad_revision='rev2',
        suspected_revisions=[],
        dimensions=['os:Mac-10.9', 'cpu:x86-64', 'pool:luci.chromium.findit'],
        cache_name='cache',
        targeted_tests={'a': ['test1']},
        urlsafe_try_job_key='urlsafe_try_job_key')
    test_try_job.OnTryJobTimeout('id', parameters)
    mock_mon.assert_called_once_with('m', 'b', 1, 'a', analysis_status.ERROR,
                                     analysis_approach_type.TRY_JOB)
