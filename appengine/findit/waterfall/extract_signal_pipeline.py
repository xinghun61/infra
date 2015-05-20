# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.api.urlfetch import ResponseTooLargeError

from pipeline_utils.appengine_third_party_pipeline_src_pipeline import pipeline

from common.http_client_appengine import HttpClientAppengine as HttpClient
from model.wf_step import WfStep
from waterfall import buildbot
from waterfall import extractors
from waterfall import lock_util
from waterfall.base_pipeline import BasePipeline


class ExtractSignalPipeline(BasePipeline):
  """A pipeline to extract failure signals from each failed step."""

  HTTP_CLIENT = HttpClient()

  # Limit stored log data to 1000 KB, because a datastore entity has a size
  # limit of 1 MB. And Leave 24 KB for other possible usage later.
  # The stored log data in datastore will be compressed with gzip, backed by
  # zlib. With the minimum compress level, the log data will usually be reduced
  # to less than 20%. So for uncompressed data, a safe limit could 4000 KB.
  LOG_DATA_BYTE_LIMIT = 4000 * 1024

  @staticmethod
  def _ExtractStorablePortionOfLog(log_data):
    # For the log of a failed step in a build, the error messages usually show
    # up at the end of the whole log. So if the log is too big to fit into a
    # datastore entity, it's safe to just save the ending portion of the log.
    if len(log_data) <= ExtractSignalPipeline.LOG_DATA_BYTE_LIMIT:
      return log_data

    lines = log_data.split('\n')
    size = 0
    for line_index in reversed(range(len(lines))):
      size += len(lines[line_index]) + 1
      if size > ExtractSignalPipeline.LOG_DATA_BYTE_LIMIT:
        return '\n'.join(lines[line_index + 1:])
    else:
      return log_data  # pragma: no cover - this won't be reached.


  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, failure_info):
    """
    Args:
      failure_info (dict): Output of pipeline DetectFirstFailurePipeline.run().

    Returns:
      A dict like below:
      {
        'step_name1': waterfall.failure_signal.FailureSignal.ToDict(),
        ...
      }
    """
    signals = {}

    master_name = failure_info['master_name']
    builder_name = failure_info['builder_name']
    build_number = failure_info['build_number']
    for step_name in failure_info.get('failed_steps', []):
      step = WfStep.Get(master_name, builder_name, build_number, step_name)
      if step and step.log_data:
        stdio_log = step.log_data
      else:
        if not lock_util.WaitUntilDownloadAllowed(
            master_name):  # pragma: no cover
          raise pipeline.Retry('Failed to pull stdio of step %s of master %s'
                               % (step_name, master_name))

        # TODO: do test-level analysis instead of step-level.
        try:
          stdio_log = buildbot.GetStepStdio(
              master_name, builder_name, build_number, step_name,
              self.HTTP_CLIENT)
        except ResponseTooLargeError:  # pragma: no cover.
          logging.exception(
              'Log of step "%s" is too large for urlfetch.', step_name)
          # If the stdio log of a step is too large, we don't want to pull it
          # again in next run, because that might lead to DDoS to the master.
          # TODO: Use archived stdio logs in Google Storage instead.
          stdio_log = 'Stdio log is too large for urlfetch.'

        if not stdio_log:  # pragma: no cover
          raise pipeline.Retry('Failed to pull stdio of step %s of master %s'
                               % (step_name, master_name))

        # Save stdio in datastore and avoid downloading again during retry.
        if not step:  # pragma: no cover
          step = WfStep.Create(
              master_name, builder_name, build_number, step_name)

        step.log_data = self._ExtractStorablePortionOfLog(stdio_log)
        try:
          step.put()
        except Exception as e:  # pragma: no cover
          # Sometimes, the stdio log is too large to save in datastore.
          logging.exception(e)

      # TODO: save result in datastore?
      signals[step_name] = extractors.ExtractSignal(
          master_name, builder_name, step_name, None, stdio_log).ToDict()

    return signals
