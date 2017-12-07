# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.findit_http_client import FinditHttpClient
from gae_libs.pipeline_wrapper import BasePipeline
from services.compile_failure import extract_compile_signal


#TODO(crbug/766851): Make this pipeline to inherit from new base pipeline.
class ExtractSignalForCompilePipeline(BasePipeline):
  """A pipeline to extract failure signals from failed compile step."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, failure_info):
    """Extracts failure signals from failed steps.

    Args:
      failure_info (dict): Output of pipeline DetectFirstFailurePipeline.run().

    Returns:
      A dict like below:
      {
        'step_name1': waterfall.failure_signal.FailureSignal.ToDict(),
        ...
      }
    """

    return extract_compile_signal.ExtractSignalsForCompileFailure(
        failure_info, FinditHttpClient())
