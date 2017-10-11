# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.findit_http_client import FinditHttpClient
from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import BasePipeline
from services.compile_failure import extract_compile_signal
from services.test_failure import extract_test_signal


class ExtractSignalPipeline(BasePipeline):
  """A pipeline to extract failure signals from each failed step."""

  HTTP_CLIENT = FinditHttpClient()

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
    if failure_info['failure_type'] == failure_type.TEST:
      return extract_test_signal.ExtractSignalsForTestFailure(
          failure_info, self.HTTP_CLIENT)

    return extract_compile_signal.ExtractSignalsForCompileFailure(
        failure_info, self.HTTP_CLIENT)
