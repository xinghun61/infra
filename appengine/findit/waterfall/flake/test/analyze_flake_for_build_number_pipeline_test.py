# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import copy
import mock

from common import constants
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from libs import time_util
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.wf_swarming_task import WfSwarmingTask

from waterfall.flake import confidence
from waterfall import swarming_util
from waterfall.flake import flake_constants
from waterfall.flake import flake_analysis_util
from waterfall.flake import lookback_algorithm
from waterfall.flake import analyze_flake_for_build_number_pipeline

from waterfall.flake.analyze_flake_for_build_number_pipeline import (
    AnalyzeFlakeForBuildNumberPipeline)
from waterfall.flake.save_last_attempted_swarming_task_id_pipeline import (
    SaveLastAttemptedSwarmingTaskIdPipeline)
from waterfall.flake.update_flake_analysis_data_points_pipeline import (
    UpdateFlakeAnalysisDataPointsPipeline)
from waterfall.flake.update_flake_bug_pipeline import UpdateFlakeBugPipeline
from waterfall.process_flake_swarming_task_result_pipeline import (
    ProcessFlakeSwarmingTaskResultPipeline)
from waterfall.trigger_flake_swarming_task_pipeline import (
    TriggerFlakeSwarmingTaskPipeline)
from waterfall.test import wf_testcase
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA


class AnalyzeFlakeForBuildNumberPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(
      flake_analysis_util, 'GetIterationsToRerun', return_value=30)
  def testAnalyzeFlakeForBuildNumberPipeline(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    iterations = 30
    timeout = 3600
    step_name = 's'
    test_name = 't'

    task_id = '1234'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.tries = 100
    task.successes = 50
    task.status = analysis_status.COMPLETED
    task.put()

    self.MockPipeline(
        TriggerFlakeSwarmingTaskPipeline,
        task_id,
        expected_args=[
            master_name, builder_name, build_number, step_name, [test_name]
        ],
        expected_kwargs={
            'iterations_to_rerun': iterations,
            'hard_timeout_seconds': timeout,
            'force': False
        })

    self.MockPipeline(
        SaveLastAttemptedSwarmingTaskIdPipeline,
        '',
        expected_args=[analysis.key.urlsafe(), task_id, build_number],
        expected_kwargs={})

    self.MockPipeline(
        ProcessFlakeSwarmingTaskResultPipeline,
        'test_result_future',
        expected_args=[
            master_name, builder_name, build_number, step_name, task_id,
            build_number, test_name, analysis.version_number
        ],
        expected_kwargs={})

    self.MockPipeline(
        UpdateFlakeAnalysisDataPointsPipeline,
        '',
        expected_args=[analysis.key.urlsafe(), build_number],
        expected_kwargs={})

    pipeline_job = AnalyzeFlakeForBuildNumberPipeline(
        analysis.key.urlsafe(), build_number, iterations, timeout)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
