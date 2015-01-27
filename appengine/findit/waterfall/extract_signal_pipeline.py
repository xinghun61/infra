# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from pipeline_utils.appengine_third_party_pipeline_src_pipeline import pipeline

from common.http_client_appengine import HttpClientAppengine as HttpClient
from model.step import Step
from waterfall import buildbot
from waterfall import extractors
from waterfall import lock_util
from waterfall.base_pipeline import BasePipeline


class ExtractSignalPipeline(BasePipeline):
  """A pipeline to extract failure signals from each failed step."""

  HTTP_CLIENT = HttpClient()

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, failure_info):
    """
    Args:
      failure_info (dict): Output of pipeline DetectFirstFailurePipeline.run().

    Returns:
      A dict like below:
      {
        'step_name1': waterfall.failure_signal.FailureSignal.ToJson(),
        ...
      }
    """
    signals = {}

    master_name = failure_info['master_name']
    builder_name = failure_info['builder_name']
    build_number = failure_info['build_number']
    for step_name in failure_info['failed_steps']:
      step = Step.GetStep(master_name, builder_name, build_number, step_name)
      if step and step.log_data:
        stdio_log = step.log_data
      else:
        if not lock_util.WaitUntilDownloadAllowed(
            master_name):  # pragma: no cover
          raise pipeline.Retry('Failed to pull stdio of step %s of master %s'
                               % (step_name, master_name))

        # TODO: do test-level analysis instead of step-level.
        stdio_log = buildbot.GetStepStdio(
            master_name, builder_name, build_number, step_name,
            self.HTTP_CLIENT)
        if not stdio_log:  # pragma: no cover
          raise pipeline.Retry('Failed to pull stdio of step %s of master %s'
                               % (step_name, master_name))

        # Save stdio in datastore and avoid downloading again during retry.
        if not step:  # pragma: no cover
          step = Step.CreateStep(
              master_name, builder_name, build_number, step_name)

        step.log_data = stdio_log
        try:
          step.put()
        except Exception as e:  # pragma: no cover
          # Sometimes, the stdio log is too large to save in datastore.
          logging.exception(e)

      # TODO: save result in datastore?
      signals[step_name] = extractors.ExtractSignal(
          master_name, builder_name, step_name, None, stdio_log).ToJson()

    return signals
