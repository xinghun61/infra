# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from libs import analysis_status
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import buildbot
from waterfall.flake import initialize_flake_pipeline
from waterfall.test import wf_testcase
from waterfall.test_info import TestInfo


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

    test = TestInfo(
        master_name, builder_name, build_number, step_name, test_name)
    need_analysis, analysis = initialize_flake_pipeline._NeedANewAnalysis(
        test, test, None, allow_new_analysis=False)

    self.assertFalse(need_analysis)
    self.assertIsNone(analysis)

  def testAnalysisIsNeededWhenNoneExistsAndAllowedToSchedule(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    step_name = 's'
    test_name = 't'

    test = TestInfo(
        master_name, builder_name, build_number, step_name, test_name)
    need_analysis, analysis = initialize_flake_pipeline._NeedANewAnalysis(
        test, test, None, allow_new_analysis=True)

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

    test = TestInfo(
        master_name, builder_name, build_number, step_name, test_name)
    need_analysis, analysis = initialize_flake_pipeline._NeedANewAnalysis(
        test, test, None, allow_new_analysis=True, force=True)

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

      test = TestInfo(
          master_name, builder_name, build_number, step_name, test_name)
      need_analysis, analysis = initialize_flake_pipeline._NeedANewAnalysis(
          test, test, None, allow_new_analysis=True, force=True)

      self.assertFalse(need_analysis)
      self.assertIsNotNone(analysis)

  @mock.patch.object(buildbot, 'GetStepLog', return_value={})
  @mock.patch(
      'waterfall.flake.initialize_flake_pipeline.RecursiveFlakePipeline')
  def testStartPipelineForNewAnalysis(self, mocked_pipeline, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    step_name = 's'
    test_name = 't'

    test = TestInfo(
        master_name, builder_name, build_number, step_name, test_name)
    analysis = initialize_flake_pipeline.ScheduleAnalysisIfNeeded(
        test, test, bug_id=None, allow_new_analysis=True, force=False,
        queue_name=constants.DEFAULT_QUEUE)

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

    test = TestInfo(
        master_name, builder_name, build_number, step_name, test_name)
    analysis = initialize_flake_pipeline.ScheduleAnalysisIfNeeded(
        test, test, queue_name=constants.DEFAULT_QUEUE)

    self.assertFalse(mocked_pipeline.called)
    self.assertIsNotNone(analysis)
