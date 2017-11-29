# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
from testing_utils import testing

from gae_libs.pipelines import pipeline_handlers
from pipelines.test_failure.heuristic_analysis_for_test_pipeline import (
    HeuristicAnalysisForTestPipeline)
from services.test_failure import test_failure_analysis


class HeuristicAnalysisForTestPipelineTest(testing.AppengineTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(
      test_failure_analysis,
      'HeuristicAnalysisForTest',
      return_value='analysis_result')
  def testHeuristicAnalysisForTestPipeline(self, _):
    pipeline = HeuristicAnalysisForTestPipeline()
    result = pipeline.run({}, True)
    self.assertEqual(result, 'analysis_result')
