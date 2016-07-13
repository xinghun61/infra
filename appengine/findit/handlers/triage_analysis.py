# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module is to handle manual triage of analysis result.

This handler will flag the analysis result as correct or incorrect.
TODO: work on an automatic or semi-automatic way to triage analysis result.
"""

import calendar
from datetime import datetime
from datetime import timedelta

from google.appengine.api import users
from google.appengine.ext import ndb
import pytz.gae

from common.base_handler import BaseHandler
from common.base_handler import Permission
from model import result_status
from model.wf_analysis import WfAnalysis
from waterfall import buildbot


MATCHING_ANALYSIS_HOURS_AGO_START = 24
MATCHING_ANALYSIS_HOURS_AGO_END = 24
MATCHING_ANALYSIS_END_BOUND_TIME_ZONE = 'US/Pacific'


def _GenPotentialCulpritTupleList(analysis):
  """Generates a list of potential culprit tuples.

  Args:
    analysis: the analysis from which to generate a potenial culript tuple list.

  Returns:
    A list of cultprit tuples that each could look like:

        (step_name, test_name, revision)

    or could look like:

        (step_name, revision)
  """
  potential_culprit_tuple_list = []

  # Iterates through the failures, tests, and suspected_cls, appending potential
  # (step_name, test_name, revision) and (step_name, revision) culprit tuples to
  # the list.
  for failure in analysis.result['failures']:
    if failure.get('tests'):
      for test in failure['tests']:
        for suspected_cl in test.get('suspected_cls', []):
          potential_culprit_tuple_list.append((
              failure['step_name'],
              test['test_name'],
              suspected_cl['revision']))
    else:
      for suspected_cl in failure['suspected_cls']:
        potential_culprit_tuple_list.append((
            failure['step_name'],
            suspected_cl['revision']))

  return potential_culprit_tuple_list


def _DoAnalysesMatch(analysis_1, analysis_2):
  """Checks if two analyses match.

  Args:
    analysis_1: The first analysis to compare.
    analysis_2: The second analysis to compare.

  Returns:
    True if the two analyses' sorted potential culprit lists match, otherwise
    False.
  """

  # Get list of potential culprit tuples.
  potential_culprit_tuple_list_1 = _GenPotentialCulpritTupleList(analysis_1)
  potential_culprit_tuple_list_2 = _GenPotentialCulpritTupleList(analysis_2)

  # Both analyses must have non-empty potential culprit lists.
  if not potential_culprit_tuple_list_1 or not potential_culprit_tuple_list_2:
    return False

  # Both analyses must have matching potential culprit lists.
  return (sorted(potential_culprit_tuple_list_1) ==
          sorted(potential_culprit_tuple_list_2))


def _AppendTriageHistoryRecord(
    analysis, is_correct, user_name, is_duplicate=False):
  """Appends a triage history record to the given analysis.

  Args:
    analysis: The analysis to which to append the history record.
    is_correct: True if the history record should indicate a correct judgement,
        otherwise False.
    user_name: The user_name of the person to include in the triage record.
    is_duplicate: Whether or not this analysis is a duplicate of another
        analysis. If this analysis is a duplicate, then set the result_status
        accordingly. If this analysis is not a duplicate, reset the reference to
        the 'first-cause' analaysis.
  """
  if is_correct:
    if analysis.suspected_cls:
      if is_duplicate:
        analysis.result_status = result_status.FOUND_CORRECT_DUPLICATE
      else:
        analysis.result_status = result_status.FOUND_CORRECT
      analysis.culprit_cls = analysis.suspected_cls
    else:
      analysis.result_status = result_status.NOT_FOUND_CORRECT
      analysis.culprit_cls = None
  else:
    analysis.culprit_cls = None
    if analysis.suspected_cls:
      if is_duplicate:
        analysis.result_status = result_status.FOUND_INCORRECT_DUPLICATE
      else:
        analysis.result_status = result_status.FOUND_INCORRECT
    else:
      analysis.result_status = result_status.NOT_FOUND_INCORRECT

  if not is_duplicate:
    # Resets the reference to the 'first-cause' triage analysis.
    # When another 'first-cause' build analysis is triaged, and this build
    # analysis is marked as a duplicate from that other 'first-cause' build
    # analysis, these are the variables that hold the reference back to that
    # 'first-cause' build analysis. It's possible that someone could then
    # manually re-triage this build analysis, in which case this build analysis
    # is no longer a duplicate, and we want to erase the reference to the
    # no-longer-relevant 'first-cause' build_analysis.
    analysis.triage_reference_analysis_master_name = None
    analysis.triage_reference_analysis_builder_name = None
    analysis.triage_reference_analysis_build_number = None

  triage_record = {
      'triage_timestamp': calendar.timegm(datetime.utcnow().timetuple()),
      'user_name': user_name,
      'result_status': analysis.result_status,
      'version': analysis.version,
  }
  if not analysis.triage_history:
    analysis.triage_history = []
  analysis.triage_history.append(triage_record)

  analysis.put()


@ndb.transactional
def _UpdateAnalysisResultStatus(
    master_name, builder_name, build_number, is_correct, user_name=None):
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  if not analysis or not analysis.completed:
    return False, None

  _AppendTriageHistoryRecord(analysis, is_correct, user_name,
                             is_duplicate=False)

  return True, analysis


def _GetDuplicateAnalyses(original_analysis):
  start_time = (original_analysis.build_start_time -
                timedelta(hours=MATCHING_ANALYSIS_HOURS_AGO_START))
  end_time = (original_analysis.build_start_time +
              timedelta(hours=MATCHING_ANALYSIS_HOURS_AGO_END))

  # Don't count any analyses from today (except for exactly at midnight local
  # time).
  # Get current time (UTC).
  current_time_as_utc = pytz.utc.localize(datetime.utcnow())

  # Convert to local time.
  current_time_as_local = current_time_as_utc.astimezone(
      pytz.timezone(MATCHING_ANALYSIS_END_BOUND_TIME_ZONE))

  # Set hours and minutes to 0 to get midnight.
  local_midnight_as_local = current_time_as_local.replace(
      hour=0, minute=0, second=0, microsecond=0)

  # Convert back to UTC time.
  local_midnight_as_utc = local_midnight_as_local.astimezone(pytz.utc)

  # Strip timezone.
  local_midnight = local_midnight_as_utc.replace(tzinfo=None)

  if end_time > local_midnight:
    end_time = local_midnight

  # Retrieve potential duplicate build analyses.
  analysis_results = WfAnalysis.query(ndb.AND(
      WfAnalysis.build_start_time >= start_time,
      WfAnalysis.build_start_time <= end_time,
      WfAnalysis.result_status == result_status.FOUND_UNTRIAGED
      )).fetch()

  # Further filter potential duplicates and return them.
  return [analysis for analysis in analysis_results if
          analysis.completed and
          analysis.result and
          _DoAnalysesMatch(original_analysis, analysis) and
          original_analysis.key is not analysis.key]


def _TriageAndCountDuplicateResults(original_analysis, is_correct,
                                    user_name=None):
  matching_analyses = _GetDuplicateAnalyses(original_analysis)

  for analysis in matching_analyses:
    analysis.triage_reference_analysis_master_name = (
        original_analysis.master_name)
    analysis.triage_reference_analysis_builder_name = (
        original_analysis.builder_name)
    analysis.triage_reference_analysis_build_number = (
        original_analysis.build_number)
    _AppendTriageHistoryRecord(analysis, is_correct, user_name,
                               is_duplicate=True)

  return len(matching_analyses)


class TriageAnalysis(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  def HandleGet(self):  # pragma: no cover
    return self.HandlePost()

  def HandlePost(self):
    """Sets the manual triage result for the analysis.

    Mark the analysis result as correct/wrong/etc.
    TODO: make it possible to set the real culprit CLs.
    """
    url = self.request.get('url').strip()
    build_info = buildbot.ParseBuildUrl(url)
    if not build_info:
      return {'data': {'success': False}}
    master_name, builder_name, build_number = build_info

    is_correct = self.request.get('correct').lower() == 'true'
    # As the permission level is CORP_USER, we could assume the current user
    # already logged in.
    user_name = users.get_current_user().email().split('@')[0]
    success, original_analysis = _UpdateAnalysisResultStatus(
        master_name, builder_name, build_number, is_correct, user_name)
    num_duplicate_analyses = 0
    if success:
      num_duplicate_analyses = _TriageAndCountDuplicateResults(
          original_analysis, is_correct, user_name)
    return {'data': {'success': success,
                     'num_duplicate_analyses': num_duplicate_analyses}}
