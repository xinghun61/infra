# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipeline_wrapper import BasePipeline
from services.test_failure import test_failure_analysis


#TODO(crbug/766851): Make this pipeline to inherit from new base pipeline.
class HeuristicAnalysisForTestPipeline(BasePipeline):
  """A pipeline to identify culprit CLs for a test failure."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, failure_info, build_completed):
    """Identifies culprit CL.

    Args:
      failure_info (dict): A dict of failure info for the current failed build
        in the following form:
      {
        "master_name": "chromium.gpu",
        "builder_name": "GPU Linux Builder"
        "build_number": 25410,
        "failed": true,
        "failed_steps": {
          "test": {
            "current_failure": 25410,
            "first_failure": 25410
          }
        },
        "builds": {
          "25410": {
            "chromium_revision": "4bffcd598dd89e0016208ce9312a1f477ff105d1"
            "blame_list": [
              "b98e0b320d39a323c81cc0542e6250349183a4df",
              ...
            ],
          }
        }
      }
      build_completed (bool): If the build is completed.

    Returns:
      analysis_result returned by build_failure_analysis.AnalyzeBuildFailure.
    """
    return test_failure_analysis.HeuristicAnalysisForTest(
        failure_info, build_completed)
