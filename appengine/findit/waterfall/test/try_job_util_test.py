# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta

from common.waterfall import failure_type
from model import analysis_status
from model.wf_build import WfBuild
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

    def _MockShouldBailOutForOutdatedBuild(*_):
      return False
    self.mock(
        try_job_util, '_ShouldBailOutForOutdatedBuild',
        _MockShouldBailOutForOutdatedBuild)

    failure_result_map = try_job_util.ScheduleTryJobIfNeeded(
        failure_info, None, None)

    self.assertFalse(_MockRootPipeline.STARTED)
    self.assertEqual({}, failure_result_map)

  def testBailOutForTestTryJob(self):
    master_name = 'master2'
    builder_name = 'builder2'
    build_number = 223
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
    master_name = 'master3'
    builder_name = 'builder3'
    build_number = 223
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
        failure_info, None, None)

    self.assertFalse(_MockRootPipeline.STARTED)
    self.assertEqual({}, failure_result_map)

  def testNotNeedANewTryJobIfNotFirstTimeFailure(self):
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

  def testNotNeedANewTryJobIfOneWithResultExists(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
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
                                     failed_steps, failure_result_map))

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
                                     failed_steps, failure_result_map))

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
                                     failed_steps, failure_result_map))

    self.assertFalse(need_try_job)
    self.assertEqual({}, failure_result_map)
    self.assertIsNone(last_pass)
    self.assertEqual(TryJobType.COMPILE, try_job_type)
    self.assertIsNone(targeted_tests)

  def testNeedANewTryJobIfTestFailureNonSwarming(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
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
                                     failed_steps, failure_result_map))

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
    failed_steps = {
        'a': {
            'current_failure': 223,
            'first_failure': 222,
            'last_pass': 221,
            'tests': {
                'a.t1': {
                    'current_failure': 223,
                    'first_failure': 223,
                    'last_pass': 221
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
                                     failed_steps, failure_result_map))

    expected_failure_result_map = {
        'a': {
            'a.t1': 'm/b/223',
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
