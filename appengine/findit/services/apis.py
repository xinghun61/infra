# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module provides service APIs within Findit."""

import logging
import pickle

from google.appengine.api import taskqueue

from common import constants
from gae_libs import appengine_util
from libs import time_util
from model.flake.analysis.flake_analysis_request import FlakeAnalysisRequest


def AnalyzeDetectedFlakeOccurrence(flake_occurrence, bug_id):
  """Analyze detected flake occurrence by Flake Detection.

  Args:
    flake_occurrece (FlakeOccurrence): A FlakeOccurrence model entity.
    bug_id (str): Id of the bug to update after the analysis finishes.
  """
  test_name = flake_occurrence.test_name
  analysis_request = FlakeAnalysisRequest.Create(test_name, False, bug_id)

  master_name = flake_occurrence.build_configuration.legacy_master_name
  builder_name = flake_occurrence.build_configuration.luci_builder
  build_number = flake_occurrence.build_configuration.legacy_build_number
  step_name = flake_occurrence.step_name
  analysis_request.AddBuildStep(master_name, builder_name, build_number,
                                step_name, time_util.GetUTCNow())

  logging.info('flake report for detected flake occurrence: %r',
               analysis_request)
  AsyncProcessFlakeReport(
      analysis_request,
      user_email=constants.DEFAULT_SERVICE_ACCOUNT,
      is_admin=False)


def AsyncProcessFlakeReport(flake_analysis_request, user_email, is_admin):
  """Pushes a task on the backend to process the flake report."""
  target = appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND)
  payload = pickle.dumps((flake_analysis_request, user_email, is_admin))
  taskqueue.add(
      url=constants.WATERFALL_PROCESS_FLAKE_ANALYSIS_REQUEST_URL,
      payload=payload,
      target=target,
      queue_name=constants.WATERFALL_FLAKE_ANALYSIS_REQUEST_QUEUE)
