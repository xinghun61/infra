# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from common import constants
from libs import analysis_status
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import buildbot
from waterfall.flake import initialize_flake_pipeline
from waterfall.test import wf_testcase
from waterfall.test_info import TestInfo


def _CreateAndSaveMasterFlakeAnalysis(master_name, builder_name, build_number,
                                      step_name, test_name, status):
  """Creates and saves a MasterFlakeAnalysis with the given information."""
  analysis = MasterFlakeAnalysis.Create(master_name, builder_name, build_number,
                                        step_name, test_name)
  analysis.status = status
  analysis.Save()
  return analysis


class InitializeFlakePipelineTest(wf_testcase.WaterfallTestCase):

  def testAnalysisIsNotNeededWhenNoneExistsAndNotAllowedToSchedule(self):
    test = TestInfo('m', 'b 1', 123, 's', 't')
    need_analysis, analysis = initialize_flake_pipeline._NeedANewAnalysis(
        test, test, None, allow_new_analysis=False)

    self.assertFalse(need_analysis)
    self.assertIsNone(analysis)

  def testAnalysisIsNeededWhenNoneExistsAndAllowedToSchedule(self):
    mocked_now = datetime(2017, 05, 01, 10, 10, 10)
    self.MockUTCNow(mocked_now)

    test = TestInfo('m', 'b 1', 123, 's', 't')
    need_analysis, analysis = initialize_flake_pipeline._NeedANewAnalysis(
        test, test, None, user_email='test@google.com', allow_new_analysis=True)

    self.assertTrue(need_analysis)
    self.assertIsNotNone(analysis)
    self.assertFalse(analysis.triggering_user_email_obscured)
    self.assertEqual(mocked_now, analysis.request_time)

  def testAnalysisIsNeededForCrashedAnalysisWithForce(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    step_name = 's'
    test_name = 't'
    _CreateAndSaveMasterFlakeAnalysis(
        master_name,
        builder_name,
        build_number,
        step_name,
        test_name,
        status=analysis_status.ERROR)

    mocked_now = datetime(2017, 05, 01, 10, 10, 10)
    self.MockUTCNow(mocked_now)

    test = TestInfo(master_name, builder_name, build_number, step_name,
                    test_name)
    need_analysis, analysis = initialize_flake_pipeline._NeedANewAnalysis(
        test,
        test,
        None,
        user_email='test@google.com',
        allow_new_analysis=True,
        force=True)

    self.assertTrue(need_analysis)
    self.assertIsNotNone(analysis)
    self.assertFalse(analysis.triggering_user_email_obscured)
    self.assertEqual(mocked_now, analysis.request_time)
    self.assertEqual(analysis.version_number, 2)

  def testAnalysisIsNeededForCompletedAnalysisWithForce(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    step_name = 's'
    test_name = 't'

    analysis = _CreateAndSaveMasterFlakeAnalysis(
        master_name,
        builder_name,
        build_number,
        step_name,
        test_name,
        status=analysis_status.COMPLETED)
    data_point = DataPoint()
    data_point.pass_rate = .5
    data_point.build_number = 100
    analysis.data_points.append(data_point)
    analysis.put()

    mocked_now = datetime(2017, 05, 01, 10, 10, 10)
    self.MockUTCNow(mocked_now)

    test = TestInfo(master_name, builder_name, build_number, step_name,
                    test_name)
    need_analysis, analysis = initialize_flake_pipeline._NeedANewAnalysis(
        test,
        test,
        None,
        user_email='test@google.com',
        allow_new_analysis=True,
        force=True)

    self.assertTrue(need_analysis)
    self.assertIsNotNone(analysis)
    self.assertFalse(analysis.triggering_user_email_obscured)
    self.assertEqual(mocked_now, analysis.request_time)
    self.assertEqual(analysis.version_number, 2)
    self.assertEqual([], analysis.data_points)

  def testAnalysisIsNotNeededForIncompleteAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    step_name = 's'
    test_name = 't'
    for status in [analysis_status.RUNNING, analysis_status.PENDING]:
      _CreateAndSaveMasterFlakeAnalysis(
          master_name,
          builder_name,
          build_number,
          step_name,
          test_name,
          status=status)

      test = TestInfo(master_name, builder_name, build_number, step_name,
                      test_name)
      need_analysis, analysis = initialize_flake_pipeline._NeedANewAnalysis(
          test, test, None, allow_new_analysis=True, force=False)

      self.assertFalse(need_analysis)
      self.assertIsNotNone(analysis)

  @mock.patch.object(buildbot, 'GetStepLog', return_value={})
  @mock.patch.object(initialize_flake_pipeline, '_NeedANewAnalysis')
  @mock.patch(
      'waterfall.flake.initialize_flake_pipeline.RecursiveFlakePipeline')
  @mock.patch('waterfall.flake.initialize_flake_pipeline.MasterFlakeAnalysis')
  def testStartPipelineForNewAnalysis(self, mocked_analysis, mocked_pipeline,
                                      mocked_need_analysis, *_):
    mocked_analysis.pipeline_status_path.return_value = 'status'
    mocked_need_analysis.return_value = (True, mocked_analysis)
    test = TestInfo('m', 'b 1', 123, 's', 't')
    analysis = initialize_flake_pipeline.ScheduleAnalysisIfNeeded(
        test,
        test,
        bug_id=None,
        allow_new_analysis=True,
        force=False,
        queue_name=constants.DEFAULT_QUEUE)

    self.assertIsNotNone(analysis)
    mocked_pipeline.assert_has_calls(
        [mock.call().start(queue_name=constants.DEFAULT_QUEUE)])

  @mock.patch('waterfall.flake.recursive_flake_pipeline.RecursiveFlakePipeline')
  def testNotStartPipelineForNewAnalysis(self, mocked_pipeline):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    step_name = 's'
    test_name = 't'

    _CreateAndSaveMasterFlakeAnalysis(
        master_name,
        builder_name,
        build_number,
        step_name,
        test_name,
        status=analysis_status.COMPLETED)

    test = TestInfo(master_name, builder_name, build_number, step_name,
                    test_name)
    analysis = initialize_flake_pipeline.ScheduleAnalysisIfNeeded(
        test, test, queue_name=constants.DEFAULT_QUEUE)

    self.assertFalse(mocked_pipeline.called)
    self.assertIsNotNone(analysis)
