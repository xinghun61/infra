# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
from testing_utils import testing

from gae_libs.pipelines import pipeline_handlers
from pipelines.compile_failure.heuristic_analysis_for_compile_pipeline import (
    HeuristicAnalysisForCompilePipeline)
from services.compile_failure import compile_failure_analysis
from services.parameters import CompileHeuristicAnalysisOutput
from services.parameters import CompileHeuristicAnalysisParameters


class HeuristicAnalysisForCompilePipelineTest(testing.AppengineTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(compile_failure_analysis, 'HeuristicAnalysisForCompile')
  def testHeuristicAnalysisForCompilePipeline(self, mock_result):
    pipeline_input = CompileHeuristicAnalysisParameters.FromSerializable({
        'failure_info': {},
        'build_completed': True
    })
    analysis_result = CompileHeuristicAnalysisOutput.FromSerializable({
        'failure_info': {},
        'signals': {},
        'heuristic_result': {}
    })
    mock_result.return_value = analysis_result
    pipeline = HeuristicAnalysisForCompilePipeline(pipeline_input)
    result = pipeline.run(pipeline_input)
    self.assertEqual(result, analysis_result.ToSerializable())
