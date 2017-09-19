# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import pipeline_handlers
from waterfall import process_swarming_tasks_result_pipeline
from waterfall.process_swarming_task_result_pipeline import (
    ProcessSwarmingTaskResultPipeline)
from waterfall.process_swarming_tasks_result_pipeline import (
    ProcessSwarmingTasksResultPipeline)
from waterfall.update_analysis_with_flake_info_pipeline import (
    UpdateAnalysisWithFlakeInfoPipeline)
from waterfall.test import wf_testcase


class ProcessSwarmingTasksResultPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testProcessSwarmingTasksResultPipeline(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 'a on platform'
    failure_info = {
        'parent_mastername': None,
        'parent_buildername': None,
        'failure_type': failure_type.TEST,
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
            step_name: {
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
            'anaother_step': {
                'first_failure': 0,
                'tests': {
                    'test1': {
                        'first_failure': 0
                    },
                }
            }
        }
    }
    build_completed = True

    self.MockPipeline(
        ProcessSwarmingTaskResultPipeline, [],
        expected_args=[master_name, builder_name, build_number, step_name],
        expected_kwargs={})

    self.MockPipeline(
        UpdateAnalysisWithFlakeInfoPipeline,
        None,
        expected_args=[master_name, builder_name, build_number, []],
        expected_kwargs={})

    pipeline = ProcessSwarmingTasksResultPipeline(
        master_name, builder_name, build_number, failure_info, build_completed)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  def testProcessSwarmingTasksResultPipelineBuildNotComplete(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    failure_info = {
        'parent_mastername': None,
        'parent_buildername': None,
        'failure_type': failure_type.TEST,
    }
    build_completed = False

    pipeline = ProcessSwarmingTasksResultPipeline(
        master_name, builder_name, build_number, failure_info, build_completed)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
