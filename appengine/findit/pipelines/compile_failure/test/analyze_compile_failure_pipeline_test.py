# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mock

from common import constants
from dto.start_waterfall_try_job_inputs import StartCompileTryJobInput
from gae_libs import pipelines
from gae_libs.pipelines import pipeline_handlers
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from pipelines import report_event_pipeline
from pipelines.compile_failure import analyze_compile_failure_pipeline
from pipelines.compile_failure.analyze_compile_failure_pipeline import (
    AnalyzeCompileFailurePipeline)
from services.parameters import BuildKey
from services.parameters import CompileHeuristicAnalysisOutput
from services.parameters import CompileHeuristicAnalysisParameters
from waterfall.test import wf_testcase


class AnalyzeCompileFailurePipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def _SetupAnalysis(self,
                     master_name,
                     builder_name,
                     build_number,
                     status=analysis_status.PENDING,
                     signals=None,
                     failure_info=None):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = status
    analysis.failure_info = failure_info
    analysis.signals = signals
    analysis.put()

  def testBuildFailurePipelineFlow(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    current_failure_info = {}

    self._SetupAnalysis(master_name, builder_name, build_number)

    heuristic_params = CompileHeuristicAnalysisParameters.FromSerializable({
        'failure_info': current_failure_info,
        'build_completed': False
    })
    heuristic_output = CompileHeuristicAnalysisOutput.FromSerializable({
        'failure_info': None,
        'signals': None,
        'heuristic_result': None
    })
    self.MockSynchronousPipeline(
        analyze_compile_failure_pipeline.HeuristicAnalysisForCompilePipeline,
        heuristic_params, heuristic_output)

    start_try_job_params = StartCompileTryJobInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        heuristic_result=heuristic_output,
        build_completed=False,
        force=False)
    self.MockGeneratorPipeline(
        analyze_compile_failure_pipeline.StartCompileTryJobPipeline,
        start_try_job_params, False)

    report_event_input = pipelines.CreateInputObjectInstance(
        report_event_pipeline.ReportEventInput,
        analysis_urlsafe_key=WfAnalysis.Get(master_name, builder_name,
                                            build_number).key.urlsafe())
    self.MockGeneratorPipeline(
        report_event_pipeline.ReportAnalysisEventPipeline, report_event_input,
        None)

    root_pipeline = AnalyzeCompileFailurePipeline(
        master_name, builder_name, build_number, current_failure_info, False,
        False)
    root_pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual(analysis_status.RUNNING, analysis.status)

  @mock.patch.object(report_event_pipeline.ReportAnalysisEventPipeline,
                     'RunImpl')
  def testBuildFailurePipelineFlowWithForce(self, mock_reporting):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    current_failure_info = {}

    self._SetupAnalysis(master_name, builder_name, build_number)

    heuristic_params = CompileHeuristicAnalysisParameters.FromSerializable({
        'failure_info': current_failure_info,
        'build_completed': False
    })
    heuristic_output = CompileHeuristicAnalysisOutput.FromSerializable({
        'failure_info': None,
        'signals': None,
        'heuristic_result': None
    })
    self.MockSynchronousPipeline(
        analyze_compile_failure_pipeline.HeuristicAnalysisForCompilePipeline,
        heuristic_params, heuristic_output)

    start_try_job_params = StartCompileTryJobInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        heuristic_result=heuristic_output,
        build_completed=False,
        force=True)
    self.MockGeneratorPipeline(
        analyze_compile_failure_pipeline.StartCompileTryJobPipeline,
        start_try_job_params, False)

    root_pipeline = AnalyzeCompileFailurePipeline(
        master_name, builder_name, build_number, current_failure_info, False,
        True)
    root_pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual(analysis_status.RUNNING, analysis.status)
    mock_reporting.assert_not_called()

  def testBuildFailurePipelineStartWithNoneResultStatus(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._SetupAnalysis(master_name, builder_name, build_number)

    root_pipeline = AnalyzeCompileFailurePipeline(
        master_name, builder_name, build_number, None, False, False)
    root_pipeline._ResetAnalysis(master_name, builder_name, build_number)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertEqual(analysis_status.RUNNING, analysis.status)
    self.assertIsNone(analysis.result_status)

  def testAnalyzeCompileFailurePipelineAbortedIfWithError(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._SetupAnalysis(
        master_name, builder_name, build_number, status=analysis_status.RUNNING)

    root_pipeline = AnalyzeCompileFailurePipeline(
        master_name, builder_name, build_number, None, False, False)
    root_pipeline._HandleUnexpectedAborting(True)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertEqual(analysis_status.ERROR, analysis.status)
    self.assertIsNone(analysis.result_status)
    self.assertTrue(analysis.aborted)

  def testAnalyzeCompileFailurePipelineNotAbortedIfWithoutError(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._SetupAnalysis(
        master_name,
        builder_name,
        build_number,
        status=analysis_status.COMPLETED)

    root_pipeline = AnalyzeCompileFailurePipeline(
        master_name, builder_name, build_number, None, False, False)
    root_pipeline._HandleUnexpectedAborting(True)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertNotEqual(analysis_status.ERROR, analysis.status)

  @mock.patch.object(logging, 'info')
  @mock.patch.object(analyze_compile_failure_pipeline,
                     'StartCompileTryJobPipeline')
  def testAnalyzeCompileFailurePipelineStartTryJob(self, mocked_pipeline,
                                                   mock_log):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    failure_info = {
        'failed_steps': {
            'compile': {
                'last_pass': 122,
                'current_failure': 123,
                'first_failure': 123
            }
        }
    }

    self._SetupAnalysis(
        master_name,
        builder_name,
        build_number,
        status=analysis_status.RUNNING,
        signals={},
        failure_info=failure_info)

    root_pipeline = AnalyzeCompileFailurePipeline(
        master_name, builder_name, build_number, None, False, False)
    root_pipeline._HandleUnexpectedAborting(True)

    heuristic_result = CompileHeuristicAnalysisOutput.FromSerializable({
        'failure_info': failure_info,
        'signals': {},
        'heuristic_result': None
    })
    start_try_job_params = StartCompileTryJobInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        heuristic_result=heuristic_result,
        build_completed=False,
        force=False)
    mocked_pipeline.assert_called_once_with(start_try_job_params)
    mocked_pipeline.assert_has_calls(
        [mock.call().start(queue_name=constants.WATERFALL_ANALYSIS_QUEUE)])
    mock_log.assert_called_once_with(
        'A try job pipeline for build %s, %s, %s starts after heuristic '
        'analysis was aborted. Check pipeline at: %s.',
        root_pipeline.master_name, root_pipeline.builder_name,
        root_pipeline.build_number, root_pipeline.pipeline_status_path())
