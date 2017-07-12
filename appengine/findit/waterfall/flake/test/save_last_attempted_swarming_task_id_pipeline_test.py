# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import constants
from gae_libs.pipeline_wrapper import pipeline_handlers
from model.flake.master_flake_analysis import MasterFlakeAnalysis

from waterfall.flake.save_last_attempted_swarming_task_id_pipeline import (
    SaveLastAttemptedSwarmingTaskIdPipeline)
from waterfall.test import wf_testcase


class SaveLastAttemptedSwarmingTaskIdPipelineTest(
    wf_testcase.WaterfallTestCase):

  app_module = pipeline_handlers._APP

  def testSaveLastAttemptedSwarmingTaskIdPipeline(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.put()

    task_id = 'task_id'
    run_build_number = 100

    pipeline_job = SaveLastAttemptedSwarmingTaskIdPipeline(
        analysis.key.urlsafe(), task_id, run_build_number)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    self.assertEqual(task_id, analysis.last_attempted_swarming_task_id)
    self.assertEqual(run_build_number, analysis.last_attempted_build_number)
