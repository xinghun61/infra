# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import logging
from urlparse import urlparse

from google.appengine.ext import ndb
from google.protobuf.timestamp_pb2 import Timestamp

from libs import analysis_status
from libs import time_util

from model.proto.gen import findit_pb2
from model.proto.gen.compile_analysis_pb2 import CompileAnalysisCompletionEvent
from model.proto.gen.test_analysis_pb2 import TestAnalysisCompletionEvent
from model.wf_try_job import WfTryJob
from model.wf_suspected_cl import WfSuspectedCL
from services import bigquery_helper
from services.flake_failure.pass_rate_util import IsFullyStable
from waterfall import waterfall_config
from waterfall.flake import triggering_sources

# Constants to report events to.
_PROJECT_ID = 'findit-for-me'
_DATASET_ID = 'events'
_TABLE_ID_TEST = 'test'
_TABLE_ID_COMPILE = 'compile'

# Culprit constants.
_DEFAULT_HOST = 'chromium-review.googlesource.com'
_DEFAULT_PROJECT = 'chromium'
_DEFAULT_REF = 'refs/heads/master'

# Start of unix epoch time.
_EPOCH_START = datetime.datetime.utcfromtimestamp(0)


def ReportCompileFailureAnalysisCompletionEvent(analysis):
  """Creates a proto from analysis and sends it to Bigquery.

  Extracts compile information into a schema proto and sends to BQ.
  """
  proto = CreateCompileFailureAnalysisCompletionEvent(analysis)
  event_id = analysis.key.urlsafe()
  return bigquery_helper.ReportEventsToBigquery(
      [(proto, event_id)], _PROJECT_ID, _DATASET_ID, _TABLE_ID_COMPILE)


def ReportTestFailureAnalysisCompletionEvent(analysis):
  """Creates a proto from analysis and sends it to Bigquery.

  Extracts test failure information into schema protos and sends them to BQ.
  """
  events_and_ids = []
  for proto in CreateTestFailureAnalysisCompletionEvent(analysis):
    events_and_ids.append((proto, analysis.key.urlsafe() + proto.test_name))
  if not events_and_ids:  # If there are no events, return.
    return None
  return bigquery_helper.ReportEventsToBigquery(events_and_ids, _PROJECT_ID,
                                                _DATASET_ID, _TABLE_ID_TEST)


def ReportTestFlakeAnalysisCompletionEvent(analysis):
  """Creates a proto from analysis and sends it to Bigquery.

  Extracts test flake information into schema protos and sends it to BQ.
  """
  proto = CreateTestFlakeAnalysisCompletionEvent(analysis)
  event_id = analysis.key.urlsafe()
  return bigquery_helper.ReportEventsToBigquery(
      [(proto, event_id)], _PROJECT_ID, _DATASET_ID, _TABLE_ID_TEST)


def _ExtractGeneralAnalysisInfo(analysis, event):
  """Extracts general information and stores it in a proto.

  Args:
    analysis (BaseBuildModel, BaseAnalysis): Analysis to be extracted from.
    event (TestAnalysisCompletionEvent,
     CompileAnalysisCompletionEvent): Event proto to be written to.
  Returns:
    Event proto given as an argument.
  """
  event.analysis_info.master_name = analysis.master_name
  event.analysis_info.builder_name = analysis.builder_name

  def unix_time(dt):
    return int((dt - _EPOCH_START).total_seconds())

  seconds = unix_time(analysis.start_time)
  event.analysis_info.timestamp.started.FromSeconds(seconds)
  seconds = unix_time(time_util.GetUTCNow())
  event.analysis_info.timestamp.completed.FromSeconds(seconds)

  event.analysis_info.detected_build_number = analysis.build_number

  return event


def _ExtractSuspectsForWfAnalysis(analysis, event):
  """Extracts information from Wf analysis and stores it in a proto.

  Args:
    (WfAnalysis): Analysis to be extracted from.
    (*AnalysisCompletionEventProto): Event proto to be written to.
  Returns:
    Event proto given as an argument.
  """
  suspects = analysis.suspected_cls or []
  for suspect in suspects:
    # Skips the culprit which is also included in this list.
    # top_score here will be None in the culprit case, so a default value
    # of 1 is used instead.
    if suspect.get('top_score', 1) is None or suspect.get('failures'):
      continue
    commit = event.analysis_info.suspects.add()
    commit.host = (urlparse(suspect.get('url', '')).netloc or _DEFAULT_HOST)
    commit.project = suspect['repo_name']
    commit.ref = _DEFAULT_REF
    commit.revision = suspect['revision']

  return event


def _ExtractCulpritForDict(culprit, event):
  """Extracts information from culprit and stores it in proto.

  Args:
    (dict): Dictionary with culprit info (compile results or test results)
    (*AnalysisCompletionEventProto): Event proto to be written to.
  """
  event.analysis_info.culprit.host = (
      urlparse(culprit['url']).netloc or _DEFAULT_HOST)
  event.analysis_info.culprit.project = culprit['repo_name']
  event.analysis_info.culprit.ref = _DEFAULT_REF
  event.analysis_info.culprit.revision = culprit['revision']


def _SetActionsForEvent(event):
  """Sets the actions for an analysis event.

  Args:
    (*AnalysisCompletionEventProto): Event proto to be written to.
  """
  if event.analysis_info.culprit.host:
    # If there's a culprit.host, then the SuspectedCL exists.
    culprit_cl = WfSuspectedCL.Get(event.analysis_info.culprit.project,
                                   event.analysis_info.culprit.revision)
    assert culprit_cl
    if culprit_cl.revert_submission_status == analysis_status.COMPLETED:
      event.analysis_info.actions.append(findit_pb2.REVERT_SUBMITTED)

    if culprit_cl.revert_status == analysis_status.COMPLETED:
      event.analysis_info.actions.append(findit_pb2.REVERT_CREATED)

    if culprit_cl.cr_notification_status == analysis_status.COMPLETED:
      event.analysis_info.actions.append(findit_pb2.CL_COMMENTED)


def _SetOutcomesForEvent(event):
  """Sets the outcomes for an analysis event.

  Args:
    (*AnalysisCompletionEventProto): Event proto to be written to.
  """
  if event.analysis_info.culprit.host:
    # Culprit was identified from a regression range.
    event.analysis_info.outcomes.append(findit_pb2.CULPRIT)

  if event.analysis_info.suspects:
    # Suspects were identified from a regression range but no culprit was found.
    event.analysis_info.outcomes.append(findit_pb2.SUSPECT)


def CreateCompileFailureAnalysisCompletionEvent(analysis):
  """Transforms a compile failure analysis to an event proto.

  Args:
    analysis (WfAnalysis): The analysis to be transformed.
  Returns:
    (CompileAnalysisCompletionEvent) Proto used to report to BQ table.
  """
  event = CompileAnalysisCompletionEvent()
  _ExtractGeneralAnalysisInfo(analysis, event)
  event.analysis_info.step_name = 'compile'

  if (analysis.failure_info and analysis.failure_info.get('failed_steps') and
      analysis.failure_info['failed_steps'].get('compile') and
      analysis.failure_info['failed_steps']['compile'].get('first_failure')):
    event.analysis_info.culprit_build_number = (
        analysis.failure_info['failed_steps']['compile']['first_failure'])

  try_job = WfTryJob.Get(analysis.master_name, analysis.builder_name,
                         event.analysis_info.culprit_build_number)
  # Culprit.
  if (try_job and try_job.compile_results and
      try_job.compile_results[-1].get('culprit') and
      try_job.compile_results[-1]['culprit'].get('compile')):
    _ExtractCulpritForDict(try_job.compile_results[-1]['culprit']['compile'],
                           event)

  event = _ExtractSuspectsForWfAnalysis(analysis, event)

  if (analysis.signals and analysis.signals.get('compile') and
      analysis.signals['compile'].get('failed_edges')):
    # Use a set to avoid adding duplicates here.
    rules = set()
    for edge in analysis.signals['compile']['failed_edges']:
      rules.add(edge['rule'])
    event.failed_build_rules.extend(rules)

  # Outcomes.
  _SetOutcomesForEvent(event)

  # Actions.
  _SetActionsForEvent(event)

  return event


def CreateTestFailureAnalysisCompletionEvent(analysis):
  """Transforms a test failure analysis into an event proto.

  Args:
    analysis (WfAnalysis): The analysis to be transformed.

  Returns:
    ([TestAnalysisCompletionEvent]) Proto used to report to BQ table.
  """
  events = []

  for step in analysis.failure_info.get('failed_steps', {}):
    for test in analysis.failure_info['failed_steps'][step].get('tests') or {}:
      if analysis.flaky_tests and test in analysis.flaky_tests.get(step, []):
        # The test is flaky, should report it in flake analysis.
        continue

      # If the failure result mapping isn't there, then bailout since it
      # contains required information.
      if (not analysis.failure_result_map or
          not analysis.failure_result_map.get(step) or
          not analysis.failure_result_map[step].get(test)):
        continue
      event = TestAnalysisCompletionEvent()
      event.flake = False
      _ExtractGeneralAnalysisInfo(analysis, event)

      event.analysis_info.step_name = step
      event.test_name = test

      # Extract master/builder/build_number from failure_result_Map.
      master, builder, build_number = (
          analysis.failure_result_map[step][test].split('/'))
      event.analysis_info.culprit_build_number = int(build_number)

      # Culprit.
      try_job = WfTryJob.Get(master, builder, build_number)
      if (try_job and try_job.test_results and
          try_job.test_results[-1].get('culprit') and
          try_job.test_results[-1]['culprit'].get(step) and
          try_job.test_results[-1]['culprit'][step].get('tests') and
          try_job.test_results[-1]['culprit'][step]['tests'].get(test)):
        _ExtractCulpritForDict(
            try_job.test_results[-1]['culprit'][step]['tests'][test], event)

      event = _ExtractSuspectsForWfAnalysis(analysis, event)

      # Outcomes.
      _SetOutcomesForEvent(event)

      # Actions.
      _SetActionsForEvent(event)

      events.append(event)

  return events


def CreateTestFlakeAnalysisCompletionEvent(analysis):
  """Transforms a flake analysis to an event proto.

  Args:
    analysis (MasterFlakeAnalysis): The analysis to be transformed.

  Returns:
    (TestAnalysisCompletionEvent) Proto used to report to BQ table.
  """
  event = TestAnalysisCompletionEvent()
  event.flake = True
  _ExtractGeneralAnalysisInfo(analysis, event)

  event.analysis_info.step_name = analysis.step_name
  event.test_name = analysis.test_name

  if analysis.suspected_flake_build_number:
    event.analysis_info.culprit_build_number = (
        analysis.suspected_flake_build_number)
    event.regression_range_confidence = analysis.confidence_in_suspected_build

  culprit_key = analysis.culprit_urlsafe_key
  culprit = None
  if culprit_key:
    culprit = ndb.Key(urlsafe=culprit_key).get()
    assert culprit
    event.analysis_info.culprit.host = _DEFAULT_HOST
    event.analysis_info.culprit.project = _DEFAULT_PROJECT
    event.analysis_info.culprit.ref = _DEFAULT_REF
    event.analysis_info.culprit.confidence = analysis.confidence_in_culprit
    event.analysis_info.culprit.revision = culprit.revision

  suspect_keys = analysis.suspect_urlsafe_keys or []
  suspects = [
      ndb.Key(urlsafe=suspect_key).get() for suspect_key in suspect_keys
  ]
  for suspect in suspects:
    commit = event.analysis_info.suspects.add()
    commit.host = _DEFAULT_HOST
    commit.project = _DEFAULT_PROJECT
    commit.ref = _DEFAULT_REF
    commit.revision = suspect.revision

  # Outcomes.

  if culprit:
    # Culprit was identified from a regression range.
    event.analysis_info.outcomes.append(findit_pb2.CULPRIT)

  if suspects:
    # Suspects were identified from a regression range but no culprit was found.
    event.analysis_info.outcomes.append(findit_pb2.SUSPECT)

  # TODO (crbug.com/805243): Track these outcomes explicitly in
  # master_flake_analysis.
  if analysis.suspected_flake_build_number is not None:
    # Regression range was found but no further findings.
    event.analysis_info.outcomes.append(findit_pb2.REGRESSION_IDENTIFIED)
  # Long standing flake.
  elif len(analysis.data_points) > 1:
    event.analysis_info.outcomes.append(findit_pb2.REPRODUCIBLE)
  # One data point and it's stable.
  elif (analysis.data_points and
        IsFullyStable(analysis.data_points[0].pass_rate)):
    # More than one datapoint is required for a reproducible result.
    event.analysis_info.outcomes.append(findit_pb2.NOT_REPRODUCIBLE)

  # Actions.
  if analysis.has_commented_on_cl:
    event.analysis_info.actions.append(findit_pb2.CL_COMMENTED)

  if analysis.has_commented_on_bug:
    event.analysis_info.actions.append(findit_pb2.BUG_COMMENTED)

  if analysis.has_filed_bug:
    event.analysis_info.actions.append(findit_pb2.BUG_CREATED)

  return event
