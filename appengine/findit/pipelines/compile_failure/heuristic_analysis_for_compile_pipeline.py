# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipelines import SynchronousPipeline
from services.compile_failure import compile_failure_analysis
from services.parameters import CompileHeuristicAnalysisOutput
from services.parameters import CompileHeuristicAnalysisParameters


class HeuristicAnalysisForCompilePipeline(SynchronousPipeline):
  """A pipeline to identify culprit CLs for a compile failure."""
  input_type = CompileHeuristicAnalysisParameters
  output_type = CompileHeuristicAnalysisOutput

  def RunImpl(self, heuristic_params):
    """Identifies culprit CL.

    Args:
      heuristic_params (CompileHeuristicAnalysisParameters): A structured object
      with 2 parts:
        failure_info (CompileFailureInfo): An object of failure info for the
        current failed build.
        build_completed (bool): If the build is completed.

    Returns:
      A CompileHeuristicAnalysisOutput object returned by
      build_failure_analysis.AnalyzeBuildFailure.
    """
    return compile_failure_analysis.HeuristicAnalysisForCompile(
        heuristic_params)