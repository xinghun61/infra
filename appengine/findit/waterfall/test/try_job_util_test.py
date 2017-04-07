# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta
import mock

from common.waterfall import failure_type
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild
from model.wf_failure_group import WfFailureGroup
from model.wf_try_job import WfTryJob
from waterfall import try_job_util
from waterfall.test import wf_testcase


class TryJobUtilTest(wf_testcase.WaterfallTestCase):

  def testShouldBailOutIfBuildHasNoStartTime(self):
    build = WfBuild.Create('m', 'b', 1)
    build.start_time = None
    self.assertTrue(try_job_util._ShouldBailOutForOutdatedBuild(build))

  def testShouldBailOutforOutdatedBuild(self):
    yesterday = datetime.utcnow() - timedelta(days=1)
    build = WfBuild.Create('m', 'b', 1)
    build.start_time = yesterday
    self.assertTrue(try_job_util._ShouldBailOutForOutdatedBuild(build))

    build.start_time = yesterday + timedelta(hours=1)
    self.assertFalse(try_job_util._ShouldBailOutForOutdatedBuild(build))

  def testNotNeedANewWaterfallTryJobIfBuilderIsNotSupportedYet(self):
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
        },
        'failure_type': failure_type.COMPILE
    }

    need_try_job, try_job_key = try_job_util.NeedANewWaterfallTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertIsNone(try_job_key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testBailOutForTestTryJob(self, mock_fn):
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

    mock_fn.return_value = False
    expected_try_job_key = WfTryJob.Create(
        master_name, builder_name, build_number).key
    need_try_job, try_job_key = try_job_util.NeedANewWaterfallTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertEqual(expected_try_job_key, try_job_key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testBailOutForTryJobWithOutdatedTimestamp(self, mock_fn):
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
        'failure_type': failure_type.COMPILE
    }

    yesterday = datetime.utcnow() - timedelta(days=1)
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.start_time = yesterday
    build.put()

    mock_fn.return_value = True

    need_try_job, try_job_key = try_job_util.NeedANewWaterfallTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertIsNone(try_job_key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewWaterfallTryJobIfNotFirstTimeFailure(self, mock_fn):
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

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    mock_fn.return_value = False
    expected_key = WfTryJob.Create(master_name, builder_name, build_number).key
    need_try_job, try_job_key = try_job_util.NeedANewWaterfallTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertEqual(expected_key, try_job_key)

  def testBlameListsIntersect(self):
    self.assertFalse(try_job_util._BlameListsIntersection(['0'], ['1']))
    self.assertFalse(try_job_util._BlameListsIntersection(['1'], []))
    self.assertFalse(try_job_util._BlameListsIntersection([], []))
    self.assertTrue(try_job_util._BlameListsIntersection(['1'], ['1']))
    self.assertTrue(try_job_util._BlameListsIntersection([
        '0', '1'], ['1', '2']))
    self.assertTrue(try_job_util._BlameListsIntersection(['1'], ['1', '2']))

  def testGetFailedStepsAndTests(self):
    failed_steps = {
        'step_c': {},
        'step_a': {
            'tests': {
                'test_c': {},
                'test_b': {},
                'test_a': {}
            },
        },
        'step_b': {}
    }

    expected_result = [
        ['step_a', 'test_a'],
        ['step_a', 'test_b'],
        ['step_a', 'test_c'],
        ['step_b', None],
        ['step_c', None]
    ]

    self.assertEqual(
        expected_result,
        try_job_util._GetStepsAndTests(failed_steps))

  def testFailedStepsAbsent(self):
    self.assertEqual([], try_job_util._GetStepsAndTests(None))

  def testNoFailedSteps(self):
    self.assertEqual([], try_job_util._GetStepsAndTests({}))

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

  def testGroupCompilesWithRelatedFailuresWithHeuristicResult(self):
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

    heuristic_result = {
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
        blame_list, None, signals, heuristic_result))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed output nodes.
    # Observe no new group creation.
    self.assertFalse(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name_2, builder_name, build_number, failure_type.COMPILE,
        blame_list, None, signals, heuristic_result))
    self.assertIsNone(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testGroupCompilesWithRelatedFailuresWithoutHeuristicResult(self):
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
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

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
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

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
                        'revision': 'rev2',
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
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

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
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

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

  def testGroupTestsWithRelatedStepsWithHeuristicResult(self):
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

    heuristic_result = {
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
        failed_steps, None, heuristic_result))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed steps.
    # Observe no new group creation.
    self.assertFalse(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name_2, builder_name, build_number, failure_type.TEST,
        blame_list, failed_steps, None, heuristic_result))
    self.assertIsNone(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testGroupTestsWithRelatedStepsWithoutHeuristicResult(self):
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
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

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
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

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
                        'revision': 'rev2',
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
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

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
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed steps.
    # Observe new group creation.
    self.assertTrue(try_job_util._IsBuildFailureUniqueAcrossPlatforms(
        master_name_2, builder_name, build_number, failure_type.TEST,
        blame_list, failed_steps_2, None, None))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewWaterfallTryJobIfOneWithResultExists(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 220
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

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.compile_results = [['rev', 'failed']]
    try_job.status = analysis_status.COMPLETED
    try_job.put()

    WfAnalysis.Create(master_name, builder_name, build_number).put()

    mock_fn.return_value = False

    need_try_job, try_job_key = try_job_util.NeedANewWaterfallTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertEqual(try_job_key, try_job.key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNeedANewWaterfallTryJobIfExistingOneHasError(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 220
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

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = analysis_status.ERROR
    try_job.put()

    WfAnalysis.Create(master_name, builder_name, build_number).put()

    mock_fn.return_value = False

    need_try_job, try_job_key = try_job_util.NeedANewWaterfallTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertTrue(need_try_job)
    self.assertEqual(try_job.key, try_job_key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewWaterfallTryJobIfNoNewFailure(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'failed_steps': {
            'a': {
                'current_failure': 223,
                'first_failure': 222,
                'last_pass': 221,
                'tests': {
                    'a.t2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    }
                }
            }
        },
        'failure_type': failure_type.TEST
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {
        'a': {
            'a.t2': 'm/b/222'
        }
    }
    analysis.put()

    mock_fn.return_value = False
    expected_try_job_key = WfTryJob.Create(
        master_name, builder_name, build_number).key

    need_try_job, try_job_key = try_job_util.NeedANewWaterfallTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertEqual(expected_try_job_key, try_job_key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNeedANewWaterfallTryJobIfTestFailureSwarming(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
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

    mock_fn.return_value = False

    need_try_job, try_job_key = try_job_util.NeedANewWaterfallTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertTrue(need_try_job)
    self.assertIsNotNone(try_job_key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNeedANewWaterfallTryJob(self, mock_fn):
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

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {
        'compile': 'm/b/223'
    }
    analysis.put()

    mock_fn.return_value = False

    need_try_job, try_job_key  = try_job_util.NeedANewWaterfallTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertTrue(need_try_job)
    self.assertIsNotNone(try_job_key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewWaterfallTryJobForOtherType(self, mock_fn):
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

    mock_fn.return_value = False
    expected_try_job_key = WfTryJob.Create(
        master_name, builder_name, build_number).key

    need_try_job, try_job_key = try_job_util.NeedANewWaterfallTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertEqual(expected_try_job_key, try_job_key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewWaterfallTryJobForCompileTypeNoFailureInfo(self, mock_fn):
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
        'failure_type': failure_type.COMPILE
    }

    mock_fn.return_value = False
    expected_try_job_key = WfTryJob.Create(
        master_name, builder_name, build_number).key
    need_try_job, try_job_key = try_job_util.NeedANewWaterfallTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertEqual(expected_try_job_key, try_job_key)

  def testForceTryJob(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'failed_steps': {
            'a': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 222,
                'tests': {
                    'a.t2': {
                        'current_failure': 223,
                        'first_failure': 223,
                        'last_pass': 222
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

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.compile_results = [['rev', 'failed']]
    try_job.status = analysis_status.COMPLETED
    try_job.put()

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {
        'a': {
            'a.t2': 'm/b/223'
        }
    }
    analysis.put()

    need_try_job, try_job_key = try_job_util.NeedANewWaterfallTryJob(
        master_name, builder_name, build_number, failure_info, None, None, True)

    self.assertTrue(need_try_job)
    self.assertEqual(try_job_key, try_job.key)

  def testRemovePlatformFromStepName(self):
    self.assertEqual('a_tests',
                     try_job_util._RemovePlatformFromStepName(
                         'a_tests on Platform'))
    self.assertEqual('a_tests',
                     try_job_util._RemovePlatformFromStepName(
                         'a_tests on Other-Platform'))
    self.assertEqual('a_tests',
                     try_job_util._RemovePlatformFromStepName('a_tests'))

  def testGetSuspectedCLsWithFailuresNoHeuristicResult(self):
    heuristic_result = None
    expected_suspected_revisions = []
    self.assertEqual(
        expected_suspected_revisions,
        sorted(try_job_util.GetSuspectedCLsWithFailures(heuristic_result)))

  def testGetSuspectedCLsWithFailuresEmptyHeuristicResult(self):
    heuristic_result = {}
    expected_suspected_revisions = []
    self.assertEqual(
        expected_suspected_revisions,
        sorted(try_job_util.GetSuspectedCLsWithFailures(heuristic_result)))

  def testGetSuspectedCLsWithFailures(self):
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
        ['step2', 'r1', None],
        ['step2', 'r2', None],
        ['step3', 'abc', 'super_test_1'],
        ['step3', 'def', 'super_test_2'],
        ['step3', 'ghi', 'super_test_2']
    ]
    self.assertEqual(
        expected_suspected_revisions,
        sorted(try_job_util.GetSuspectedCLsWithFailures(heuristic_result)))

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
        try_job_util.GetFailedTargetsFromSignals(signals, 'm', 'b'),
        ['a', 'b'])

  def testGetFailedTargetsFromSignals(self):
    self.assertEqual(
        try_job_util.GetFailedTargetsFromSignals({}, 'm', 'b'), [])

    self.assertEqual(
        try_job_util.GetFailedTargetsFromSignals({'compile': {}}, 'm', 'b'),
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
        try_job_util.GetFailedTargetsFromSignals(signals, 'm', 'b'), ['a.exe'])

  def testUseObjectFilesAsFailedTargetIfStrictRegexUsed(self):
    signals = {
        'compile': {
            'failed_targets': [
                {'source': 'b.cc', 'target': 'b.o'},
            ]
        }
    }

    self.assertEqual(
        try_job_util.GetFailedTargetsFromSignals(
            signals, 'master1', 'builder1'),
        ['b.o'])
