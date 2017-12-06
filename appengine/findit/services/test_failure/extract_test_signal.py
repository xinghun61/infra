# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for extracting test failure signals.

It provides functions to:
  * Extract failure signals for test failure
"""

import base64
import json
import logging

from model.wf_step import WfStep
from services import extract_signal
from services import gtest
from waterfall import extractors
from waterfall import swarming_util
from waterfall import waterfall_config
from waterfall.failure_signal import FailureSignal


def ExtractSignalsForTestFailure(failure_info, http_client):
  signals = {}

  master_name = failure_info['master_name']
  builder_name = failure_info['builder_name']
  build_number = failure_info['build_number']

  for step_name in failure_info.get('failed_steps', {}):
    failure_log = None
    if not waterfall_config.StepIsSupportedForMaster(step_name, master_name):
      # Bail out if the step is not supported.
      continue

    # 1. Tries to get stored failure log from step.
    step = (WfStep.Get(master_name, builder_name, build_number, step_name) or
            WfStep.Create(master_name, builder_name, build_number, step_name))
    if step.log_data:
      failure_log = step.log_data
    else:
      json_formatted_log = True
      # 2. Gets gtest results.
      list_isolated_data = failure_info['failed_steps'][step_name].get(
          'list_isolated_data', [])
      gtest_result = swarming_util.RetrieveShardedTestResultsFromIsolatedServer(
          list_isolated_data, http_client)
      if gtest_result:
        failure_log = gtest.GetConsistentTestFailureLog(gtest_result)

      if not gtest_result or failure_log in [
          gtest.INVALID_FAILURE_LOG, gtest.WRONG_FORMAT_LOG
      ]:
        # 3. Gets stdout log.
        json_formatted_log = False
        failure_log = extract_signal.GetStdoutLog(
            master_name, builder_name, build_number, step_name, http_client)

      if not failure_log:
        raise Exception('Failed to pull stdio of step %s of master %s' %
                        (step_name, master_name))

      # Save step log in datastore and avoid downloading again during retry.
      # TODO(chanli): add a new field "is_json_data" to the WfStep to indicate
      # format of the log.
      step.log_data = extract_signal.ExtractStorablePortionOfLog(
          failure_log, json_formatted_log)

      try:
        step.put()
      except Exception as e:  # pragma: no cover
        # Sometimes, the step log is too large to save in datastore.
        logging.exception(e)

    if step.isolated:
      try:
        json_failure_log = (json.loads(failure_log)
                            if failure_log != gtest.FLAKY_FAILURE_LOG else {})
      except ValueError:
        json_failure_log = {}
        logging.warning('failure_log %s is not valid JSON.' % failure_log)

      signals[step_name] = {'tests': {}}
      step_signal = FailureSignal()

      for test_name, test_failure_log in json_failure_log.iteritems():
        signals[step_name]['tests'][test_name] = extractors.ExtractSignal(
            master_name, builder_name, step_name, test_name,
            base64.b64decode(test_failure_log)).ToDict()

        # Save signals in test failure log to step level.
        step_signal.MergeFrom(signals[step_name]['tests'][test_name])

      signals[step_name]['files'] = step_signal.files
    else:
      signals[step_name] = extractors.ExtractSignal(
          master_name, builder_name, step_name, None, failure_log).ToDict()

  return signals
