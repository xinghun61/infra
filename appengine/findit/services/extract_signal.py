# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for extracting failure signals.

It provides fuctions to:
  * Extract failure signals for compile failure
  * Extract failure signals for test failures at step level and test level
"""

import base64
import json
import logging

from google.appengine.api.urlfetch import ResponseTooLargeError

from model.wf_analysis import WfAnalysis
from model.wf_step import WfStep
from services import gtest
from waterfall import buildbot
from waterfall import extractors
from waterfall import waterfall_config
from waterfall.failure_signal import FailureSignal

# Limit stored log data to 1000 KB, because a datastore entity has a size
# limit of 1 MB. And Leave 24 KB for other possible usage later.
# The stored log data in datastore will be compressed with gzip, backed by
# zlib. With the minimum compress level, the log data will usually be reduced
# to less than 20%. So for uncompressed data, a safe limit could 4000 KB.
LOG_DATA_BYTE_LIMIT = 4000 * 1024


def _ExtractStorablePortionOfLog(log_data, from_ninja_output=False):
  # For the log of a failed step in a build, the error messages usually show
  # up at the end of the whole log. So if the log is too big to fit into a
  # datastore entity, it's safe to just save the ending portion of the log.
  if len(log_data) <= LOG_DATA_BYTE_LIMIT:
    return log_data
  if from_ninja_output:
    return ''

  lines = log_data.split('\n')
  size = 0
  for line_index in reversed(range(len(lines))):
    size += len(lines[line_index]) + 1
    if size > LOG_DATA_BYTE_LIMIT:
      return '\n'.join(lines[line_index + 1:])
  else:
    return log_data  # pragma: no cover - this won't be reached.


def _GetStdoutLog(master_name, builder_name, build_number, step_name,
                  http_client):
  try:
    return buildbot.GetStepLog(master_name, builder_name, build_number,
                               step_name, http_client)

  except ResponseTooLargeError:
    logging.exception('Log of step "%s" is too large for urlfetch.', step_name)
    # If the stdio log of a step is too large, we don't want to pull
    # it again in next run, because that might lead to DDoS to the
    # master.
    return 'Stdio log is too large for urlfetch.'


def ExtractSignals(failure_info, http_client):
  signals = {}

  master_name = failure_info['master_name']
  builder_name = failure_info['builder_name']
  build_number = failure_info['build_number']

  for step_name in failure_info.get('failed_steps', []):
    if not waterfall_config.StepIsSupportedForMaster(step_name, master_name):
      # Bail out if the step is not supported.
      continue

    step = WfStep.Get(master_name, builder_name, build_number, step_name)
    if step and step.log_data:
      failure_log = step.log_data
    else:
      # TODO: do test-level analysis instead of step-level.
      # TODO: Use swarming test result instead of archived gtest results
      gtest_result = buildbot.GetGtestResultLog(master_name, builder_name,
                                                build_number, step_name)
      from_ninja_output = False
      if gtest_result:
        failure_log = gtest.GetConsistentTestFailureLog(gtest_result)

      if gtest_result is None or failure_log == 'invalid':
        use_ninja_output_log = (waterfall_config.GetDownloadBuildDataSettings()
                                .get('use_ninja_output_log'))
        if step_name == 'compile' and use_ninja_output_log:
          failure_log = buildbot.GetStepLog(
              master_name, builder_name, build_number, step_name, http_client,
              'json.output[ninja_info]')
          from_ninja_output = True
        if (step_name != 'compile' or not use_ninja_output_log or
            not failure_log):
          from_ninja_output = False
          failure_log = _GetStdoutLog(master_name, builder_name, build_number,
                                      step_name, http_client)

        if not failure_log:
          raise Exception('Failed to pull stdio of step %s of master %s' %
                          (step_name, master_name))

      # Save step log in datastore and avoid downloading again during retry.
      if not step:  # pragma: no cover
        step = WfStep.Create(master_name, builder_name, build_number, step_name)

      step.log_data = _ExtractStorablePortionOfLog(failure_log,
                                                   from_ninja_output)

      try:
        step.put()
      except Exception as e:  # pragma: no cover
        # Sometimes, the step log is too large to save in datastore.
        logging.exception(e)

    # TODO: save result in datastore?
    if step.isolated:
      try:
        json_failure_log = (json.loads(failure_log)
                            if failure_log != 'flaky' else {})
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
      signals[step_name]['keywords'] = step_signal.keywords
    else:
      signals[step_name] = extractors.ExtractSignal(
          master_name, builder_name, step_name, None, failure_log).ToDict()

  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  analysis.signals = signals
  analysis.put()

  return signals
