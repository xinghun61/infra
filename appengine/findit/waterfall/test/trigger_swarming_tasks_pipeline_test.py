# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline_handlers
from model.wf_analysis import WfAnalysis
from waterfall import build_util
from waterfall import trigger_swarming_task_pipeline
from waterfall import trigger_swarming_tasks_pipeline
from waterfall.test import wf_testcase
from waterfall.trigger_swarming_tasks_pipeline import (
    TriggerSwarmingTasksPipeline)


class TriggerSwarmingTasksPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def test_GetStepsThatNeedToTriggerSwarmingTasksNoAnalysis(self):
    result = (
        trigger_swarming_tasks_pipeline._GetStepsThatNeedToTriggerSwarmingTasks(
            'm', 'b', 1, {}))
    self.assertEqual(result, {})

  def test_GetStepsThatNeedToTriggerSwarmingTasksNoFailureResultMap(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 2
    WfAnalysis.Create(master_name, builder_name, build_number).put()

    failure_info = {
        'failed': True,
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 2,
        'chromium_revision': None,
        'builds': {
            2: {
                'blame_list': [],
                'chromium_revision': None
            }
        },
        'failed_steps': {
            'abc_test': {
                'current_failure': 2,
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'Unittest2.Subtest1': {
                        'current_failure': 2,
                        'first_failure': 2,
                        'last_pass': 1,
                        'base_test_name': 'Unittest2.Subtest1'
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 2,
                        'first_failure': 1,
                        'last_pass': 0,
                        'base_test_name': 'Unittest3.Subtest2'
                    }
                }
            },
            'a_test': {
                'current_failure': 2,
                'first_failure': 1,
                'last_pass': 0,
            }
        },
        'failure_type': failure_type.TEST
    }

    expected_result = {
        'abc_test': ['Unittest2.Subtest1']
    }
    expected_failure_result_map = {
        'abc_test': {
            'Unittest2.Subtest1': build_util.CreateBuildId(
                master_name, builder_name, build_number),
            'Unittest3.Subtest2': build_util.CreateBuildId(
                master_name, builder_name, 1)
        }
    }

    result = (
        trigger_swarming_tasks_pipeline._GetStepsThatNeedToTriggerSwarmingTasks(
            master_name, builder_name, build_number, failure_info))
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)

    self.assertEqual(result, expected_result)
    self.assertEqual(analysis.failure_result_map, expected_failure_result_map)

  def test_GetStepsThatNeedToTriggerSwarmingTasks(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 2
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {
        'a_tests': {
            'Unittest1.Subtest1': 'm/b/1'
        }
    }
    analysis.put()

    failure_info = {
        'failed': True,
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 2,
        'chromium_revision': None,
        'builds': {
            2: {
                'blame_list': [],
                'chromium_revision': None
            }
        },
        'failed_steps': {
            'abc_test': {
                'current_failure': 2,
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'Unittest2.Subtest1': {
                        'current_failure': 2,
                        'first_failure': 2,
                        'last_pass': 1,
                        'base_test_name': 'Unittest2.Subtest1'
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 2,
                        'first_failure': 1,
                        'last_pass': 0,
                        'base_test_name': 'Unittest3.Subtest2'
                    }
                }
            },
            'a_tests': {
                'current_failure': 2,
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'Unittest1.Subtest1': {
                        'current_failure': 2,
                        'first_failure': 1,
                        'last_pass': 0,
                        'base_test_name': 'Unittest3.Subtest2'
                    }
                }
            }
        },
        'failure_type': failure_type.TEST
    }

    expected_result = {
        'abc_test': ['Unittest2.Subtest1']
    }
    result = (
        trigger_swarming_tasks_pipeline._GetStepsThatNeedToTriggerSwarmingTasks(
            master_name, builder_name, build_number, failure_info))
    self.assertEqual(result, expected_result)

  def testTriggerSwarmingTasksPipelineNoFailureInfo(self):
    class _MockedTriggerSwarmingTaskPipeline(BasePipeline):
      count = 0
      def run(self, *_):  # pragma: no cover
        _MockedTriggerSwarmingTaskPipeline.count += 1
    self.mock(trigger_swarming_task_pipeline, 'TriggerSwarmingTaskPipeline',
              _MockedTriggerSwarmingTaskPipeline)
    pipeline = TriggerSwarmingTasksPipeline('m', 'b', 1, {})
    pipeline.start()
    self.execute_queued_tasks()
    self.assertEqual(_MockedTriggerSwarmingTaskPipeline.count, 0)

  def testTriggerSwarmingTasksPipelineCompile(self):
    class _MockedTriggerSwarmingTaskPipeline(BasePipeline):
      count = 0
      def run(self, *_):  # pragma: no cover
        _MockedTriggerSwarmingTaskPipeline.count += 1
    self.mock(trigger_swarming_task_pipeline, 'TriggerSwarmingTaskPipeline',
              _MockedTriggerSwarmingTaskPipeline)
    failure_info = {
        'failed': True,
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 2,
        'chromium_revision': None,
        'builds': {
            2: {
                'blame_list': [],
                'chromium_revision': None
            }
        },
        'failed_steps': {
            'compile': {
                'current_failure': 2,
                'first_failure': 1,
                'last_pass': 0,
            }
        },
        'failure_type': failure_type.COMPILE
    }
    pipeline = TriggerSwarmingTasksPipeline('m', 'b', 2, failure_info)
    pipeline.start()
    self.execute_queued_tasks()
    self.assertEqual(_MockedTriggerSwarmingTaskPipeline.count, 0)

  def testTriggerSwarmingTasksPipeline(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 2
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {
        'a_tests': {
            'Unittest1.Subtest1': 'm/b/1'
        }
    }
    analysis.put()

    failure_info = {
        'failed': True,
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 2,
        'chromium_revision': None,
        'builds': {
            2: {
                'blame_list': [],
                'chromium_revision': None
            }
        },
        'failed_steps': {
            'abc_test': {
                'current_failure': 2,
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'Unittest2.Subtest1': {
                        'current_failure': 2,
                        'first_failure': 2,
                        'last_pass': 1,
                        'base_test_name': 'Unittest2.Subtest1'
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 2,
                        'first_failure': 1,
                        'last_pass': 0,
                        'base_test_name': 'Unittest3.Subtest2'
                    }
                }
            },
            'a_tests': {
                'current_failure': 2,
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'Unittest1.Subtest1': {
                        'current_failure': 2,
                        'first_failure': 1,
                        'last_pass': 0,
                        'base_test_name': 'Unittest3.Subtest2'
                    }
                }
            }
        },
        'failure_type': failure_type.TEST
    }

    class _MockedTriggerSwarmingTaskPipeline(BasePipeline):
      count = 0
      def run(self, *_):
        _MockedTriggerSwarmingTaskPipeline.count += 1
    self.mock(trigger_swarming_task_pipeline, 'TriggerSwarmingTaskPipeline',
              _MockedTriggerSwarmingTaskPipeline)
    pipeline = TriggerSwarmingTasksPipeline(
        master_name, builder_name, build_number, failure_info)
    pipeline.start()
    self.execute_queued_tasks()
    self.assertEqual(_MockedTriggerSwarmingTaskPipeline.count, 1)
