# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from common.pipeline_wrapper import pipeline_handlers
from model import analysis_status
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall.flake import initialize_flake_pipeline
from waterfall.test import wf_testcase


class InitializeFlakePipelineTest(wf_testcase.WaterfallTestCase):

  def _CreateAndSaveMasterFlakeAnalysis(
      self, master_name, builder_name, build_number,
      step_name, test_name, status):
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.status = status
    analysis.Save()

  def testAnalysisIsNotNeededWhenNoneExistsAndNotAllowedToSchedule(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    step_name = 's'
    test_name = 't'

    need_analysis, analysis = initialize_flake_pipeline._NeedANewAnalysis(
        master_name, builder_name, build_number, step_name, test_name, None,
        allow_new_analysis=False)

    self.assertFalse(need_analysis)
    self.assertIsNone(analysis)

  def testAnalysisIsNeededWhenNoneExistsAndAllowedToSchedule(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    step_name = 's'
    test_name = 't'

    need_analysis, analysis = initialize_flake_pipeline._NeedANewAnalysis(
        master_name, builder_name, build_number, step_name, test_name, None,
        allow_new_analysis=True)

    self.assertTrue(need_analysis)
    self.assertIsNotNone(analysis)

  def testAnalysisIsNeededForCrashedAnalysisWithForce(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    step_name = 's'
    test_name = 't'
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=analysis_status.ERROR)

    need_analysis, analysis = initialize_flake_pipeline._NeedANewAnalysis(
        master_name, builder_name, build_number, step_name, test_name, None,
        allow_new_analysis=True, force=True)

    self.assertTrue(need_analysis)
    self.assertIsNotNone(analysis)
    self.assertTrue(analysis.version_number > 1)

  def testAnalysisIsNotNeededForIncompletedAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    step_name = 's'
    test_name = 't'
    for status in [analysis_status.RUNNING, analysis_status.PENDING]:
      self._CreateAndSaveMasterFlakeAnalysis(
          master_name, builder_name, build_number,
          step_name, test_name, status=status)

      need_analysis, analysis = initialize_flake_pipeline._NeedANewAnalysis(
          master_name, builder_name, build_number, step_name, test_name, None,
          allow_new_analysis=True, force=True)

      self.assertFalse(need_analysis)
      self.assertIsNotNone(analysis)

  @mock.patch(
      'waterfall.flake.initialize_flake_pipeline.RecursiveFlakePipeline')
  def testStartPipelineForNewAnalysis(self, mocked_pipeline):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    step_name = 's'
    test_name = 't'

    analysis = initialize_flake_pipeline.ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number,
        step_name, test_name, allow_new_analysis=True, force=False,
        queue_name=constants.DEFAULT_QUEUE)

    self.assertIsNotNone(analysis)
    mocked_pipeline.assert_has_calls(
        [mock.call().StartOffPSTPeakHours(queue_name=constants.DEFAULT_QUEUE)])

  @mock.patch(
      'waterfall.flake.recursive_flake_pipeline.RecursiveFlakePipeline')
  def testNotStartPipelineForNewAnalysis(self, mocked_pipeline):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    step_name = 's'
    test_name = 't'

    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name, test_name,
        status=analysis_status.COMPLETED)

    analysis = initialize_flake_pipeline.ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number,
        step_name, test_name,
        queue_name=constants.DEFAULT_QUEUE)

    self.assertFalse(mocked_pipeline.called)
    self.assertIsNotNone(analysis)
