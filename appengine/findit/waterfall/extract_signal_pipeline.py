# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import cStringIO
import json
import logging

from google.appengine.api.urlfetch import ResponseTooLargeError

from common.http_client_appengine import HttpClientAppengine as HttpClient
from model.wf_step import WfStep
from pipeline_wrapper import BasePipeline
from pipeline_wrapper import pipeline
from waterfall import buildbot
from waterfall import extractors
from waterfall import lock_util
from waterfall import waterfall_config


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

  @staticmethod
  def _GetReliableTestFailureLog(gtest_result):
    """Analyze the archived gtest json results and extract reliable failures.

    Args:
      gtest_result (str): A JSON file for failed step log.

    Returns:
      A string contains the names of reliable test failures and related
      log content.
      If gtest_results in gtest json result is 'invalid', we will return
      'invalid' as the result.
      If we find out that all the test failures in this step are flaky, we will
      return 'flaky' as result.
    """
    step_failure_data = json.loads(gtest_result)

    if step_failure_data['gtest_results'] == 'invalid':  # pragma: no cover
      return 'invalid'

    sio = cStringIO.StringIO()
    for iteration in step_failure_data['gtest_results']['per_iteration_data']:
      for test_name in iteration.keys():
        is_reliable_failure = True

        for test_run in iteration[test_name]:
          # We will ignore the test if some of the attempts were success.
          if test_run['status'] == 'SUCCESS':
            is_reliable_failure = False
            break

        if is_reliable_failure:  # all attempts failed
          for test_run in iteration[test_name]:
            sio.write(base64.b64decode(test_run['output_snippet_base64']))

    failed_test_log = sio.getvalue()
    sio.close()

    if not failed_test_log:
      return 'flaky'

    return failed_test_log

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
    signals = {}
    if not failure_info['failed'] or not failure_info['chromium_revision']:
      # Bail out if no failed step or no chromium revision.
      return signals

    master_name = failure_info['master_name']
    builder_name = failure_info['builder_name']
    build_number = failure_info['build_number']
    for step_name in failure_info.get('failed_steps', []):
      if not waterfall_config.IsStepSupportedForMaster(step_name, master_name):
        # Bail out if the step is not supported.
        continue

      step = WfStep.Get(master_name, builder_name, build_number, step_name)
      if step and step.log_data:
        failure_log = step.log_data
      else:
        # TODO: do test-level analysis instead of step-level.
        # TODO: Use swarming test result instead of archived gtest results
        gtest_result = buildbot.GetGtestResultLog(
            master_name, builder_name, build_number, step_name)
        if gtest_result:
          failure_log = self._GetReliableTestFailureLog(gtest_result)

        if gtest_result is None or failure_log == 'invalid':
          if not lock_util.WaitUntilDownloadAllowed(
              master_name):  # pragma: no cover
            raise pipeline.Retry('Failed to pull log of step %s of master %s'
                                 % (step_name, master_name))
          try:
            failure_log = buildbot.GetStepStdio(
                master_name, builder_name, build_number, step_name,
                self.HTTP_CLIENT)
          except ResponseTooLargeError:  # pragma: no cover.
            logging.exception(
                'Log of step "%s" is too large for urlfetch.', step_name)
            # If the stdio log of a step is too large, we don't want to pull it
            # again in next run, because that might lead to DDoS to the master.
            # TODO: Use archived stdio logs in Google Storage instead.
            failure_log = 'Stdio log is too large for urlfetch.'

          if not failure_log:  # pragma: no cover
            raise pipeline.Retry('Failed to pull stdio of step %s of master %s'
                                 % (step_name, master_name))

        # Save step log in datastore and avoid downloading again during retry.
        if not step:  # pragma: no cover
          step = WfStep.Create(
              master_name, builder_name, build_number, step_name)

        step.log_data = self._ExtractStorablePortionOfLog(failure_log)

        try:
          step.put()
        except Exception as e:  # pragma: no cover
          # Sometimes, the step log is too large to save in datastore.
          logging.exception(e)

      # TODO: save result in datastore?
      signals[step_name] = extractors.ExtractSignal(
          master_name, builder_name, step_name, None, failure_log).ToDict()
    return signals
