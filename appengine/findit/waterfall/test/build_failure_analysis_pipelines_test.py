# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from testing_utils import testing

from common import constants
from model.wf_analysis import WfAnalysis
from model import analysis_status
from pipeline_wrapper import pipeline_handlers
from waterfall import build_failure_analysis_pipelines


class _MockRootPipeline(object):
  STARTED = False

  def __init__(self, master_name, builder_name, build_number, build_completed):
    pass

  def pipeline_status_path(self):
    return ''

  def start(self, queue_name):
    _MockRootPipeline.STARTED = True
    logging.info(queue_name)


class BuildFailureAnalysisPipelinesTest(testing.AppengineTestCase):
  app_module = pipeline_handlers._APP

  def _CreateAndSaveWfAnalysis(
      self, master_name, builder_name, build_number, not_passed_steps, status,
      build_completed=True):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.not_passed_steps = not_passed_steps
    analysis.status = status
    analysis.build_completed = build_completed
    analysis.put()

  def testAnalysisIsNeededWhenBuildWasNeverAnalyzed(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    failed_steps = ['a']

    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, False, False)

    self.assertTrue(need_analysis)

  def testNewAnalysisIsNotNeededWhenNotForcedAfterCompletedAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    not_passed_steps = ['a', 'b']
    self._CreateAndSaveWfAnalysis(master_name, builder_name, build_number,
                                  not_passed_steps, analysis_status.COMPLETED)

    failed_steps = ['a', 'b']
    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, False, False)

    self.assertFalse(need_analysis)

  def testNewAnalysisIsNotNeededWhenForcedBeforeCompletedAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    not_passed_steps = []
    self._CreateAndSaveWfAnalysis(
        master_name, builder_name, build_number,
        not_passed_steps, analysis_status.RUNNING)

    failed_steps = ['a']
    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, False, True)

    self.assertFalse(need_analysis)

  def testNewAnalysisIsNeededWhenForcedAfterCompletedAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    not_passed_steps = ['a']
    self._CreateAndSaveWfAnalysis(
        master_name, builder_name, build_number,
        not_passed_steps, analysis_status.COMPLETED)

    failed_steps = ['a']
    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, False, True)

    self.assertTrue(need_analysis)

  def testNewAnalysisIsNotNeededWhenFailedStepsNotProvided(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    not_passed_steps = ['a']
    self._CreateAndSaveWfAnalysis(
        master_name, builder_name, build_number,
        not_passed_steps, analysis_status.COMPLETED)

    failed_steps = None
    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, False, False)

    self.assertFalse(need_analysis)

  def testNewAnalysisIsNotNeededWhenNewFailedStepsBeforeCompletedAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    not_passed_steps = ['a']
    self._CreateAndSaveWfAnalysis(
        master_name, builder_name, build_number,
        not_passed_steps, analysis_status.RUNNING)

    failed_steps = ['a', 'b']
    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, False, False)

    self.assertFalse(need_analysis)

  def testNewAnalysisIsNeededWhenNewFailedStepsAfterCompletedAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    not_passed_steps = ['a']
    self._CreateAndSaveWfAnalysis(
        master_name, builder_name, build_number,
        not_passed_steps, analysis_status.COMPLETED)

    failed_steps = ['a', 'b']
    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, False, False)

    self.assertTrue(need_analysis)

  def testNewAnalysisIsNeededWhenBuildCompletedAfterLastAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    not_passed_steps = ['a']
    self._CreateAndSaveWfAnalysis(
        master_name, builder_name, build_number,
        not_passed_steps, analysis_status.COMPLETED, build_completed=False)

    failed_steps = ['a']
    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, True, False)

    self.assertTrue(need_analysis)

  def testStartPipelineForNewAnalysis(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self.mock(build_failure_analysis_pipelines.analyze_build_failure_pipeline,
              'AnalyzeBuildFailurePipeline',
              _MockRootPipeline)
    _MockRootPipeline.STARTED = False

    build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number, failed_steps=['a'],
        build_completed=False, force=False, queue_name=constants.DEFAULT_QUEUE)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)

    self.assertTrue(_MockRootPipeline.STARTED)
    self.assertIsNotNone(analysis)

  def testNotStartPipelineForNewAnalysis(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    not_passed_steps = ['a']

    self._CreateAndSaveWfAnalysis(
        master_name, builder_name, build_number,
        not_passed_steps, analysis_status.RUNNING)

    self.mock(build_failure_analysis_pipelines.analyze_build_failure_pipeline,
              'AnalyzeBuildFailurePipeline',
              _MockRootPipeline)
    _MockRootPipeline.STARTED = False

    build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number, failed_steps=['a'],
        build_completed=True, force=False, queue_name=constants.DEFAULT_QUEUE)

    self.assertFalse(_MockRootPipeline.STARTED)
