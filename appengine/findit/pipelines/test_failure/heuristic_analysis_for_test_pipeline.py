# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipelines import SynchronousPipeline
from services.parameters import TestHeuristicAnalysisOutput
from services.parameters import TestHeuristicAnalysisParameters
from services.test_failure import test_failure_analysis


class HeuristicAnalysisForTestPipeline(SynchronousPipeline):
  """A pipeline to identify culprit CLs for a test failure."""
  input_type = TestHeuristicAnalysisParameters
  output_type = TestHeuristicAnalysisOutput

  def RunImpl(self, heuristic_params):
    """Identifies culprit CL.

    Args:
      heuristic_params (TestHeuristicAnalysisParameters): A structured object
      with 2 fields:
        failure_info (TestFailureInfo): An object of failure info for the
        current failed build.
        build_completed (bool): If the build is completed.

    Returns:
      A TestHeuristicAnalysisOutput object returned by
      test_failure_analysis.HeuristicAnalysisForTest.
    """
    return test_failure_analysis.HeuristicAnalysisForTest(heuristic_params)
