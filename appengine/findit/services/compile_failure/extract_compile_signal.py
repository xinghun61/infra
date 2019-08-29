# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for extracting compile failure signals.

It provides functions to:
  * Extract failure signals for compile failure
"""

import logging

from services import extract_signal
from services import step_util
from waterfall import extractors
from waterfall import waterfall_config

use_datastore = True
try:
  from model.wf_step import WfStep
except ImportError:
  # If the v1 models are not available, simply skip datastore operations (used
  # to save failure logs between retries).
  use_datastore = False


def ExtractSignalsForCompileFailure(failure_info, http_client):
  signals = {}

  master_name = failure_info.master_name
  builder_name = failure_info.builder_name
  build_number = failure_info.build_number
  step_name = 'compile'

  if step_name not in (failure_info.failed_steps or {}):
    logging.debug(
        'No compile failure found when extracting signals for failed '
        'build %s/%s/%d', master_name, builder_name, build_number)
    return signals

  if not failure_info.failed_steps[step_name].supported:
    # Bail out if the step is not supported.
    logging.info('Findit could not analyze compile failure for master %s.',
                 master_name)
    return signals

  failure_log = None
  if use_datastore:
    # 1. Tries to get stored failure log from step.
    step = (
        WfStep.Get(master_name, builder_name, build_number, step_name) or
        WfStep.Create(master_name, builder_name, build_number, step_name))
    if step.log_data:
      failure_log = step.log_data
  if not failure_log:
    # 2. Tries to get ninja_output as failure log.
    from_ninja_output = False
    use_ninja_output_log = (
        waterfall_config.GetDownloadBuildDataSettings()
        .get('use_ninja_output_log'))
    if use_ninja_output_log:
      failure_log = step_util.GetWaterfallBuildStepLog(
          master_name, builder_name, build_number, step_name, http_client,
          'json.output[ninja_info]')
      from_ninja_output = True

    if not failure_log:
      # 3. Tries to get stdout log for compile step.
      from_ninja_output = False
      failure_log = extract_signal.GetStdoutLog(
          master_name, builder_name, build_number, step_name, http_client)

    try:
      if not failure_log:
        raise extract_signal.FailedToGetFailureLogError(
            'Failed to pull failure log (stdio or ninja output) of step %s of'
            ' %s/%s/%d' % (step_name, master_name, builder_name, build_number))
    except extract_signal.FailedToGetFailureLogError:
      return {}

    if use_datastore:
      # Save step log in datastore and avoid downloading again during retry.
      step.log_data = extract_signal.ExtractStorablePortionOfLog(
          failure_log, from_ninja_output)
      try:
        step.put()
      except Exception as e:  # pragma: no cover
        # Sometimes, the step log is too large to save in datastore.
        logging.exception(e)

  signals[step_name] = extractors.ExtractSignal(
      master_name,
      builder_name,
      step_name,
      test_name=None,
      failure_log=failure_log).ToDict()

  extract_signal.SaveSignalInAnalysis(master_name, builder_name, build_number,
                                      signals)

  return signals
