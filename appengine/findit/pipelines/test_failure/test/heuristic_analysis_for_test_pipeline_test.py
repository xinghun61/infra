# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
from testing_utils import testing

from gae_libs.pipelines import pipeline_handlers
from pipelines.test_failure.heuristic_analysis_for_test_pipeline import (
    HeuristicAnalysisForTestPipeline)
from services.parameters import TestHeuristicAnalysisOutput
from services.parameters import TestHeuristicAnalysisParameters
from services.test_failure import test_failure_analysis


class HeuristicAnalysisForTestPipelineTest(testing.AppengineTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(test_failure_analysis, 'HeuristicAnalysisForTest')
  def testHeuristicAnalysisForTestPipeline(self, mock_result):
    pipeline_input = TestHeuristicAnalysisParameters.FromSerializable({
        'failure_info': {},
        'build_completed': True
    })
    analysis_result = TestHeuristicAnalysisOutput.FromSerializable({
        'failure_info': {},
        'heuristic_result': {}
    })
    mock_result.return_value = analysis_result
    pipeline = HeuristicAnalysisForTestPipeline(pipeline_input)
    result = pipeline.run(pipeline_input)
    self.assertEqual(analysis_result.ToSerializable(), result)
