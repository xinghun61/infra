# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from common.pipeline_wrapper import pipeline_handlers
from model import analysis_status
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall.flake.initialize_flake_pipeline import NeedANewAnalysis
from waterfall.flake.initialize_flake_pipeline import ScheduleAnalysisIfNeeded
from waterfall.test import wf_testcase


class InitializeFlakePipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

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

    need_analysis = NeedANewAnalysis(
        master_name, builder_name, build_number, step_name, test_name,
        allow_new_analysis=False)

    self.assertFalse(need_analysis)

  def testAnalysisIsNeededWhenNoneExistsAndAllowedToSchedule(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    step_name = 's'
    test_name = 't'

    need_analysis = NeedANewAnalysis(
        master_name, builder_name, build_number, step_name, test_name,
        allow_new_analysis=True)

    self.assertTrue(need_analysis)

  def testAnalysisIsNeededAfterCrashedAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    step_name = 's'
    test_name = 't'
    status = analysis_status.ERROR
    self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status=status)

    need_analysis = NeedANewAnalysis(
        master_name, builder_name, build_number, step_name, test_name)

    self.assertTrue(need_analysis)

  def testAnalysisIsNotNeededAfterCompletedAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    step_name = 's'
    test_name = 't'
    for status in [analysis_status.RUNNING,
                   analysis_status.PENDING,
                   analysis_status.COMPLETED]:
      self._CreateAndSaveMasterFlakeAnalysis(
          master_name, builder_name, build_number,
          step_name, test_name, status=status)

      need_analysis = NeedANewAnalysis(
          master_name, builder_name, build_number, step_name, test_name)

      self.assertFalse(need_analysis)

  def testAnalysisIsNeededAfterCompletedDifferentAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    step_name = 's'
    test_name = 't'
    for status in [analysis_status.RUNNING,
                   analysis_status.PENDING,
                   analysis_status.COMPLETED]:
      self._CreateAndSaveMasterFlakeAnalysis(
          master_name, builder_name, build_number,
          step_name, test_name, status=status)

    dif_test_name = 'd'
    need_analysis = NeedANewAnalysis(
        master_name, builder_name, build_number, step_name, dif_test_name,
        allow_new_analysis=True)

    self.assertTrue(need_analysis)

  @mock.patch(
      'waterfall.flake.initialize_flake_pipeline.RecursiveFlakePipeline')
  def testStartPipelineForNewAnalysis(self, mocked_pipeline):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    step_name = 's'
    test_name = 't'

    ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number,
        step_name, test_name, allow_new_analysis=True,
        queue_name=constants.DEFAULT_QUEUE)

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    self.assertIsNotNone(analysis)
    mocked_pipeline.assert_has_calls(
        [mock.call().start(queue_name=constants.DEFAULT_QUEUE)])

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

    ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number,
        step_name, test_name,
        queue_name=constants.DEFAULT_QUEUE)

    self.assertFalse(mocked_pipeline.called)
