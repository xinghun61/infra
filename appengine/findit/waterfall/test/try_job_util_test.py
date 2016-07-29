# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta

from common.waterfall import failure_type
from model import analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild
from model.wf_failure_group import WfFailureGroup
from model.wf_try_job import WfTryJob
from waterfall import try_job_util
from waterfall.test import wf_testcase
from waterfall.try_job_type import TryJobType


class _MockRootPipeline(object):
  STARTED = False

  def __init__(self, *_):
    pass

  def start(self, *_, **__):
    _MockRootPipeline.STARTED = True

  @property
  def pipeline_status_path(self):
    return 'path'


class TryJobUtilTest(wf_testcase.WaterfallTestCase):

  def testNotNeedANewTryJobIfBuilderIsNotSupportedYet(self):
    master_name = 'master3'
    builder_name = 'builder3'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {
            'compile': {
                'current_failure': 221,
                'first_failure': 221,
                'last_pass': 220
            }
        },
        'builds': {
            '220': {
                'blame_list': ['220-1', '220-2'],
                'chromium_revision': '220-2'
            },
            '221': {
                'blame_list': ['221-1', '221-2'],
                'chromium_revision': '221-2'
            },
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        }
    }

    self.mock(
        try_job_util.swarming_tasks_to_try_job_pipeline,
        'SwarmingTasksToTryJobPipeline', _MockRootPipeline)
    _MockRootPipeline.STARTED = False

    failure_result_map = try_job_util.ScheduleTryJobIfNeeded(
        failure_info, None, None)

    self.assertFalse(_MockRootPipeline.STARTED)
    self.assertEqual({}, failure_result_map)

  def testBailOutForTestTryJob(self):
    master_name = 'master2'
    builder_name = 'builder2'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {
            'a_test': {}
        },
        'failure_type': failure_type.TEST
    }

    def _MockShouldBailOutForOutdatedBuild(*_):
      return False
    self.mock(
        try_job_util, '_ShouldBailOutForOutdatedBuild',
        _MockShouldBailOutForOutdatedBuild)

    failure_result_map = try_job_util.ScheduleTryJobIfNeeded(
        failure_info, None, None)

    self.assertEqual({}, failure_result_map)

  def testBailOutForTryJobWithOutdatedTimestamp(self):
    master_name = 'master1'
    builder_name = 'builder1'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {
            'compile': {
                'current_failure': 221,
                'first_failure': 221,
                'last_pass': 220
            }
        },
    }

    yesterday = datetime.utcnow() - timedelta(days=1)
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.start_time = yesterday
    build.put()

    self.mock(
        try_job_util.swarming_tasks_to_try_job_pipeline,
        'SwarmingTasksToTryJobPipeline', _MockRootPipeline)
    _MockRootPipeline.STARTED = False

    def _MockShouldBailOutForOutdatedBuild(*_):
      return True

    self.mock(
        try_job_util, '_ShouldBailOutForOutdatedBuild',
        _MockShouldBailOutForOutdatedBuild)

    failure_result_map = try_job_util.ScheduleTryJobIfNeeded(
        failure_info, None, None, False)

    self.assertFalse(_MockRootPipeline.STARTED)
    self.assertEqual({}, failure_result_map)

  def testForceTryJob(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 222
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
        'failure_type': failure_type.COMPILE
    }

    self.mock(
        try_job_util.swarming_tasks_to_try_job_pipeline,
        'SwarmingTasksToTryJobPipeline', _MockRootPipeline)
    _MockRootPipeline.STARTED = False

    try_job_util.ScheduleTryJobIfNeeded(failure_info, None, None, True)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    self.assertTrue(_MockRootPipeline.STARTED)
    self.assertIsNotNone(try_job)

  def testNotNeedANewTryJobIfNotFirstTimeFailure(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 221,
                'last_pass': 220
            }
        },
        'builds': {
            '220': {
                'blame_list': ['220-1', '220-2'],
                'chromium_revision': '220-2'
            },
            '221': {
                'blame_list': ['221-1', '221-2'],
                'chromium_revision': '221-2'
            },
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.COMPILE
    }

    self.mock(
        try_job_util.swarming_tasks_to_try_job_pipeline,
        'SwarmingTasksToTryJobPipeline', _MockRootPipeline)
    _MockRootPipeline.STARTED = False

    def _MockShouldBailOutForOutdatedBuild(*_):
      return False

    self.mock(
        try_job_util, '_ShouldBailOutForOutdatedBuild',
        _MockShouldBailOutForOutdatedBuild)

    try_job_util.ScheduleTryJobIfNeeded(failure_info, None, None)

    self.assertFalse(_MockRootPipeline.STARTED)

  def testBlameListsIntersect(self):
    self.assertFalse(try_job_util._BlameListsIntersection(['0'], ['1']))
    self.assertFalse(try_job_util._BlameListsIntersection(['1'], []))
    self.assertFalse(try_job_util._BlameListsIntersection([], []))
    self.assertTrue(try_job_util._BlameListsIntersection(['1'], ['1']))
    self.assertTrue(try_job_util._BlameListsIntersection([
        '0', '1'], ['1', '2']))
    self.assertTrue(try_job_util._BlameListsIntersection(['1'], ['1', '2']))

  def testGetFailedSteps(self):
    failed_steps = {
        'step_a': {
            'tests': {
                'Test1': {}
            },
        },
        'step_b': {}
    }

    expected_result = {
        'step_a': ['Test1'],
        'step_b': []
    }

    self.assertEqual(
        expected_result,
        try_job_util._GetStepsAndTests(failed_steps))

  def testFailedStepsAbsent(self):
    self.assertEqual({}, try_job_util._GetStepsAndTests(None))

  def testNoFailedSteps(self):
    self.assertEqual({}, try_job_util._GetStepsAndTests({}))

  def testLinkAnalysisToBuildFailureGroup(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    failure_group_key = ['m2', 'b2', 2]
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    try_job_util._LinkAnalysisToBuildFailureGroup(
        master_name, builder_name, build_number, failure_group_key)
    self.assertEqual(
        failure_group_key,
        WfAnalysis.Get(
            master_name, builder_name, build_number).failure_group_key)

  def testDoNotGroupUnknownBuildFailure(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with UNKNOWN failure.
    # Observe that the build failure is unique, but there is no new group
    # creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, failure_type.UNKNOWN,
        None, None, None, None))
    self.assertIsNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

  def testDoNotGroupInfraBuildFailure(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with INFRA failure.
    # Observe that the build failure is unique, but there is no new group
    # creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, failure_type.INFRA,
        None, None, None, None))
    self.assertIsNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

  def testDoNotGroupCompileWithNoOutputNodes(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    blame_list = ['a']

    signals = {
        'compile': {
            'failed_output_nodes': []
        }
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have zero failed output nodes.
    # Observe that the build failure is unique, but there is no new group
    # creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, failure_type.COMPILE,
        blame_list, None, signals, None))
    self.assertIsNone(WfFailureGroup.Get(
        master_name, builder_name, build_number))

  def testAnalysisFailureGroupKeySet(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    blame_list = ['a']

    signals = {
        'compile': {
            'failed_output_nodes': [
                'abc.obj'
            ]
        }
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, failure_type.COMPILE,
        blame_list, None, signals, None))

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual(
        [master_name, builder_name, build_number], analysis.failure_group_key)

  def testSecondAnalysisFailureGroupKeySet(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']

    signals = {
        'compile': {
            'failed_output_nodes': [
                'abc.obj'
            ]
        }
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, failure_type.COMPILE,
        blame_list, None, signals, None))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed output nodes.
    # Observe no new group creation.
    self.assertFalse(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name_2, builder_name, build_number, failure_type.COMPILE,
        blame_list, None, signals, None))

    analysis_2 = WfAnalysis.Get(master_name_2, builder_name, build_number)
    self.assertEqual(
        [master_name, builder_name, build_number], analysis_2.failure_group_key)

  def testGroupCompilesWithRelatedFailures(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']

    signals = {
        'compile': {
            'failed_output_nodes': [
                'abc.obj'
            ]
        }
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, failure_type.COMPILE,
        blame_list, None, signals, None))
    self.assertTrue(WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed output nodes.
    # Observe no new group creation.
    self.assertFalse(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name_2, builder_name, build_number, failure_type.COMPILE,
        blame_list, None, signals, None))
    self.assertIsNone(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupCompilesWithDisjointBlameLists(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list_1 = ['a']

    blame_list_2 = ['b']

    signals = {
        'compile': {
            'failed_output_nodes': [
                'abc.obj'
            ]
        }
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, failure_type.COMPILE,
        blame_list_1, None, signals, None))
    self.assertTrue(WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed output nodes.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name_2, builder_name, build_number, failure_type.COMPILE,
        blame_list_2, None, signals, None))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupCompilesWithDifferentHeuristicResults(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']

    signals = {
        'compile': {
            'failed_output_nodes': [
                'abc.obj'
            ]
        }
    }

    heuristic_result_1 = {
        'failures': [
            {
                'step_name': 'step1',
                'suspected_cls': [
                    {
                        'revision': 'rev1',
                    }
                ],
            }
        ]
    }

    heuristic_result_2 = {
        'failures': [
            {
                'step_name': 'step1',
                'suspected_cls': [
                    {
                        'revision': 'rev1',
                    }
                ],
            }
        ]
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, failure_type.COMPILE,
        blame_list, None, signals,
        heuristic_result_1))
    self.assertTrue(WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed output nodes.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name_2, builder_name, build_number, failure_type.COMPILE,
        blame_list, None, signals, heuristic_result_2))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupCompilesWithDifferentOutputNodes(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']

    signals_1 = {
        'compile': {
            'failed_output_nodes': [
                'abc.obj'
            ]
        }
    }

    signals_2 = {
        'compile': {
            'failed_output_nodes': [
                'def.obj'
            ]
        }
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, failure_type.COMPILE,
        blame_list, None, signals_1, None))
    self.assertTrue(WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed output nodes.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name_2, builder_name, build_number, failure_type.COMPILE,
        blame_list, None, signals_2, None))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupTestWithNoSteps(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    blame_list = ['a']

    failed_steps = {}

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have zero failed steps.
    # Observe that the build failure is unique, but there is no new group
    # creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, failure_type.TEST, blame_list,
        failed_steps, None, None))
    self.assertIsNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

  def testGroupTestsWithRelatedSteps(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']

    failed_steps = {
        'step_a': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed steps.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, failure_type.TEST, blame_list,
        failed_steps, None, None))
    self.assertTrue(WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed steps.
    # Observe no new group creation.
    self.assertFalse(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name_2, builder_name, build_number, failure_type.TEST,
        blame_list, failed_steps, None, None))
    self.assertIsNone(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupTestsWithDisjointBlameLists(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list_1 = ['a']
    blame_list_2 = ['b']
    failed_steps = {
        'step_a': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed steps.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, failure_type.TEST,
        blame_list_1, failed_steps, None,
        None))
    self.assertTrue(WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed steps.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name_2, builder_name, build_number, failure_type.TEST,
        blame_list_2, failed_steps, None, None))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupTestsWithDifferentHeuristicResults(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']
    failed_steps = {
        'step_a': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    }

    heuristic_result_1 = {
        'failures': [
            {
                'step_name': 'step1',
                'suspected_cls': [
                    {
                        'revision': 'rev1',
                    }
                ],
            }
        ]
    }

    heuristic_result_2 = {
        'failures': [
            {
                'step_name': 'step1',
                'suspected_cls': [
                    {
                        'revision': 'rev1',
                    }
                ],
            }
        ]
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed steps.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, failure_type.TEST, blame_list,
        failed_steps, None, heuristic_result_1))
    self.assertTrue(WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed steps.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name_2, builder_name, build_number, failure_type.TEST,
        blame_list, failed_steps, None, heuristic_result_2))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupTestsWithDifferentSteps(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']

    failed_steps_1 = {
        'step_a': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    }

    failed_steps_2 = {
        'step_b': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed steps.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, failure_type.TEST, blame_list,
        failed_steps_1, None, None))
    self.assertTrue(WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed steps.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name_2, builder_name, build_number, failure_type.TEST,
        blame_list, failed_steps_2, None, None))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testNeedANewTryJobForFirstFailureInGroup(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    builds = {
        str(build_number): {
            'blame_list': ['a']
        }
    }
    failed_steps = {
        'compile': {
            'current_failure': 223,
            'first_failure': 223,
            'last_pass': 220
        }
    }
    signals = {
        'compile': {
            'failed_output_nodes': [
                'abc.obj'
            ]
        }
    }

    # Run _NeedANewTryJob with signals that have certain failed output nodes.
    # Observe a need for a new try job.
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    need_try_job, _, _, _ = try_job_util._NeedANewTryJob(
        master_name, builder_name, build_number, failure_type.COMPILE,
        failed_steps, {}, builds, signals, None)
    self.assertTrue(need_try_job)

  def testNotNeedANewTryJobForSecondFailureInGroup(self):
    master_name = 'm'
    master_name_2 = 'm2'
    builder_name = 'b'
    build_number = 223
    builds = {
        str(build_number): {
            'blame_list': ['a']
        }
    }
    failed_steps = {
        'compile': {
            'current_failure': 223,
            'first_failure': 223,
            'last_pass': 220
        }
    }

    signals = {
        'compile': {
            'failed_output_nodes': [
                'abc.obj'
            ]
        }
    }

    # Run _NeedANewTryJob with signals that have certain failed output nodes.
    # This should create a new wf_failure_group.
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    try_job_util._NeedANewTryJob(
        master_name, builder_name, build_number, failure_type.COMPILE,
        failed_steps, {}, builds, signals, None)
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    # Run _NeedANewTryJob with signals that have the same failed output nodes.
    # Observe no need for a new try job.
    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    need_try_job, _, _, _ = try_job_util._NeedANewTryJob(
        master_name_2, builder_name, build_number, failure_type.COMPILE,
        failed_steps, {}, builds, signals, None)
    self.assertFalse(need_try_job)

  def testNotNeedANewTryJobIfOneWithResultExists(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    builds = {
        str(build_number): {
            'blame_list': ['a']
        }
    }
    failed_steps = {
        'compile': {
            'current_failure': 223,
            'first_failure': 223,
            'last_pass': 220
        }
    }

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.compile_results = [['rev', 'failed']]
    try_job.status = analysis_status.COMPLETED
    try_job.put()

    failure_result_map = {}
    need_try_job, last_pass, try_job_type, targeted_tests = (
        try_job_util._NeedANewTryJob(master_name, builder_name, build_number,
                                     failure_type.COMPILE, failed_steps,
                                     failure_result_map, builds, None, None))

    expected_failure_result_map = {
        'compile': 'm/b/223'
    }

    self.assertFalse(need_try_job)
    self.assertEqual(expected_failure_result_map, failure_result_map)
    self.assertEqual(220, last_pass)
    self.assertEqual(TryJobType.COMPILE, try_job_type)
    self.assertIsNone(targeted_tests)

  def testNeedANewTryJobIfExistingOneHasError(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    builds = {
        str(build_number): {
            'blame_list': ['a']
        }
    }
    failed_steps = {
        'compile': {
            'current_failure': 223,
            'first_failure': 223,
            'last_pass': 220
        }
    }

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = analysis_status.ERROR
    try_job.put()

    failure_result_map = {}
    need_try_job, last_pass, try_job_type, targeted_tests = (
        try_job_util._NeedANewTryJob(master_name, builder_name, build_number,
                                     failure_type.COMPILE, failed_steps,
                                     failure_result_map, builds, None, None))

    expected_failure_result_map = {
        'compile': 'm/b/223'
    }
    self.assertTrue(need_try_job)
    self.assertEqual(expected_failure_result_map, failure_result_map)
    self.assertEqual(220, last_pass)
    self.assertEqual(TryJobType.COMPILE, try_job_type)
    self.assertIsNone(targeted_tests)

  def testNotNeedANewTryJobIfLastPassCannotDetermine(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    builds = {
        str(build_number): {
            'blame_list': ['a']
        }
    }
    failed_steps = {
        'compile': {
            'current_failure': 223,
            'first_failure': 223
        }
    }

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = analysis_status.ERROR
    try_job.put()

    failure_result_map = {}
    need_try_job, last_pass, try_job_type, targeted_tests = (
        try_job_util._NeedANewTryJob(master_name, builder_name, build_number,
                                     failure_type.COMPILE, failed_steps,
                                     failure_result_map, builds, None, None))

    self.assertFalse(need_try_job)
    self.assertEqual({}, failure_result_map)
    self.assertIsNone(last_pass)
    self.assertEqual(TryJobType.COMPILE, try_job_type)
    self.assertIsNone(targeted_tests)

  def testNeedANewTryJobIfTestFailureNonSwarming(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    builds = {
        str(build_number): {
            'blame_list': ['a']
        }
    }
    failed_steps = {
        'a': {
            'current_failure': 223,
            'first_failure': 223,
            'last_pass': 222
        },
        'b': {
            'current_failure': 223,
            'first_failure': 222,
            'last_pass': 221
        }
    }

    failure_result_map = {}
    need_try_job, last_pass, try_job_type, targeted_tests = (
        try_job_util._NeedANewTryJob(master_name, builder_name, build_number,
                                     failure_type.TEST, failed_steps,
                                     failure_result_map, builds, None, None))

    expected_failure_result_map = {
        'a': 'm/b/223',
        'b': 'm/b/222'
    }

    expected_targeted_tests = {
        'a': []
    }

    self.assertTrue(need_try_job)
    self.assertEqual(expected_failure_result_map, failure_result_map)
    self.assertEqual(222, last_pass)
    self.assertEqual('test', try_job_type)
    self.assertEqual(expected_targeted_tests, targeted_tests)

  def testNeedANewTryJobIfTestFailureSwarming(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    builds = {
        str(build_number): {
            'blame_list': ['a']
        }
    }
    failed_steps = {
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
    }

    failure_result_map = {}
    need_try_job, last_pass, try_job_type, targeted_tests = (
        try_job_util._NeedANewTryJob(master_name, builder_name, build_number,
                                     failure_type.TEST, failed_steps,
                                     failure_result_map, builds, None, None))

    expected_failure_result_map = {
        'a': {
            'a.PRE_t1': 'm/b/223',
            'a.t2': 'm/b/222',
            'a.t3': 'm/b/223'
        },
        'b': {
            'b.t1': 'm/b/222',
            'b.t2': 'm/b/222'
        },
    }

    expected_targeted_tests = {
        'a': ['a.t1', 'a.t3']
    }

    self.assertTrue(need_try_job)
    self.assertEqual(expected_failure_result_map, failure_result_map)
    self.assertEqual(221, last_pass)
    self.assertEqual('test', try_job_type)
    self.assertEqual(expected_targeted_tests, targeted_tests)

  def testNeedANewTryJob(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 222
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
        'failure_type': failure_type.COMPILE
    }

    self.mock(
        try_job_util.swarming_tasks_to_try_job_pipeline,
        'SwarmingTasksToTryJobPipeline', _MockRootPipeline)
    _MockRootPipeline.STARTED = False

    def _MockShouldBailOutForOutdatedBuild(*_):
      return False

    self.mock(
        try_job_util, '_ShouldBailOutForOutdatedBuild',
        _MockShouldBailOutForOutdatedBuild)

    try_job_util.ScheduleTryJobIfNeeded(failure_info, None, None)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    self.assertTrue(_MockRootPipeline.STARTED)
    self.assertIsNotNone(try_job)

  def testUseFailedOutputNodesFromSignals(self):
    signals = {
        'compile': {
            'failed_targets': [
                {'target': 'a.exe'},
                {'source': 'b.cc', 'target': 'b.o'},
            ],
            'failed_output_nodes': ['a', 'b'],
        }
    }

    self.assertEqual(
        try_job_util._GetFailedTargetsFromSignals(signals, 'm', 'b'),
        ['a', 'b'])

  def testGetFailedTargetsFromSignals(self):
    self.assertEqual(
        try_job_util._GetFailedTargetsFromSignals({}, 'm', 'b'), [])

    self.assertEqual(
        try_job_util._GetFailedTargetsFromSignals({'compile': {}}, 'm', 'b'),
        [])

    signals = {
        'compile': {
            'failed_targets': [
                {'target': 'a.exe'},
                {'source': 'b.cc',
                 'target': 'b.o'}]
        }
    }

    self.assertEqual(
        try_job_util._GetFailedTargetsFromSignals(signals, 'm', 'b'), ['a.exe'])

  def testUseObjectFilesAsFailedTargetIfStrictRegexUsed(self):
    signals = {
        'compile': {
            'failed_targets': [
                {'source': 'b.cc', 'target': 'b.o'},
            ]
        }
    }

    self.assertEqual(
        try_job_util._GetFailedTargetsFromSignals(
            signals, 'master1', 'builder1'),
        ['b.o'])

  def testGenPotentialCulpritTupleListNoHeuristicResult(self):
    heuristic_result = None
    expected_suspected_revisions = []
    self.assertEqual(
        expected_suspected_revisions,
        sorted(try_job_util.GenPotentialCulpritTupleList(heuristic_result)))

  def testGenPotentialCulpritTupleListEmptyHeuristicResult(self):
    heuristic_result = {}
    expected_suspected_revisions = []
    self.assertEqual(
        expected_suspected_revisions,
        sorted(try_job_util.GenPotentialCulpritTupleList(heuristic_result)))

  def testGenPotentialCulpritTupleList(self):
    heuristic_result = {
        'failures': [
            {
                'step_name': 'step1',
                'suspected_cls': [],
            },
            {
                'step_name': 'step2',
                'suspected_cls': [
                    {
                        'revision': 'r1',
                    },
                    {
                        'revision': 'r2',
                    },
                ],
            },
            {
                'step_name': 'step3',
                'suspected_cls': [
                    {
                        'revision': 'r3',
                    }
                ],
                'tests': [
                    {
                        'test_name': 'super_test_1',
                        'suspected_cls': [
                            {
                                'revision': 'abc'
                            }
                        ]
                    },
                    {
                        'test_name': 'super_test_2',
                        'suspected_cls': [
                            {
                                'revision': 'def'
                            },
                            {
                                'revision': 'ghi'
                            }
                        ]
                    }
                ]
            }
        ]
    }
    expected_suspected_revisions = [
        ('step2', 'r1', None),
        ('step2', 'r2', None),
        ('step3', 'abc', 'super_test_1'),
        ('step3', 'def', 'super_test_2'),
        ('step3', 'ghi', 'super_test_2')
    ]
    self.assertEqual(
        expected_suspected_revisions,
        sorted(try_job_util.GenPotentialCulpritTupleList(heuristic_result)))

  def testGetSuspectsFromHeuristicResultForCompile(self):
    heuristic_result = {
        'failures': [
            {
                'step_name': 'compile',
                'suspected_cls': [
                    {
                        'revision': 'r1',
                    },
                    {
                        'revision': 'r2',
                    },
                ],
            },
        ]
    }
    expected_suspected_revisions = ['r1', 'r2']
    self.assertEqual(
        expected_suspected_revisions,
        try_job_util._GetSuspectsFromHeuristicResult(heuristic_result))

  def testGetSuspectsFromHeuristicResultForTest(self):
    heuristic_result = {
        'failures': [
            {
                'step_name': 'step1',
                'suspected_cls': [
                    {
                        'revision': 'r1',
                    },
                    {
                        'revision': 'r2',
                    },
                ],
            },
            {
                'step_name': 'step2',
                'suspected_cls': [
                    {
                        'revision': 'r1',
                    },
                    {
                        'revision': 'r3',
                    },
                ],
            },
        ]
    }
    expected_suspected_revisions = ['r1', 'r2', 'r3']
    self.assertEqual(
        expected_suspected_revisions,
        try_job_util._GetSuspectsFromHeuristicResult(heuristic_result))

  def testShouldBailOutforOutdatedBuild(self):
    yesterday = datetime.utcnow() - timedelta(days=1)
    build = WfBuild.Create('m', 'b', 1)
    build.start_time = yesterday
    self.assertTrue(try_job_util._ShouldBailOutForOutdatedBuild(build))

    build.start_time = yesterday + timedelta(hours=1)
    self.assertFalse(try_job_util._ShouldBailOutForOutdatedBuild(build))
