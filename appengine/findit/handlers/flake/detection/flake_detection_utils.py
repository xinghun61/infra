# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Util functions for flake detection handlers."""

from collections import defaultdict
import logging

from libs import time_util
from libs import analysis_status
from model import entity_util
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from model.flake.flake_type import FlakeType
from model.flake.flake_type import FLAKE_TYPE_DESCRIPTIONS


def _GetOccurrenceInformation(occurrence):
  """Gets information of one occurrence in a dict.

  Args:
    occurrence(FlakeOccurrence): one flake occurrence.

  Returns:
    (dict): Information of one occurrence in a dict.
  """
  occurrence_dict = occurrence.to_dict()

  # JavaScript numbers are always stored as double precision floating point
  # numbers, where the number (the fraction) is stored in bits 0 to 51, the
  # exponent in bits 52 to 62, and the sign in bit 63. So integers are
  # accurate up to 15 digits. To keep the precision of build ids (int 64),
  # convert them to string before rendering HTML pages.
  occurrence_dict['build_id'] = str(occurrence.build_id)

  # Formats the times in string representations with UTC.
  occurrence_dict['time_happened'] = time_util.FormatDatetime(
      occurrence_dict['time_happened'])
  occurrence_dict['time_detected'] = time_util.FormatDatetime(
      occurrence_dict['time_detected'])
  occurrence_dict['flake_type'] = FLAKE_TYPE_DESCRIPTIONS.get(
      occurrence_dict['flake_type'], 'Unknown')

  return occurrence_dict


def _ToList(grouped_occurrences_dict):
  """Converts grouped_occurrences from a dict to a list, and sort the groups by
    the most recent occurrence time, in descending order.

  dom_repeat only accepts array but not json, so converts the
  grouped_occurrences_dict to a list.

  Args:
    grouped_occurrences_dict(dict): A dict of grouped occurrence dicts. Like
      {
          'group1': [
              occurrence1_dict,
              occurrence2_dict
          ],
          'group2': [
              occurrence3_dict,
              occurrence4_dict
          ]
      }

  Returns:
    (list): A list of grouped occurrence dicts. Like
    [
        {
            'group_by_field': 'group1',
            'occurrences': [
                occurrence1_dict,
                occurrence2_dict
            ]
        },
        {
            'group_by_field': 'group2',
            'occurrences': [
                occurrence3_dict,
                occurrence4_dict
            ]
        }
    ]
  """
  grouped_occurrences_by_most_recent_occurrence = [{
      'group_by_field': group_by_field,
      'occurrences': occurrences
  } for group_by_field, occurrences in grouped_occurrences_dict.iteritems()]

  grouped_occurrences_by_most_recent_occurrence.sort(
      key=lambda e: e['occurrences'][0]['time_happened'], reverse=True)

  return grouped_occurrences_by_most_recent_occurrence


def _GetGroupedOccurrencesByBuilder(occurrences):
  """Groups occurrences by builder.

  Args:
    occurrences(list): A list of FlakeOccurrence objects.

  Returns:
    (dict): A dict of lists for occurrences grouped by builder.
  """
  occurrences_dict = defaultdict(list)

  for occurrence in occurrences:
    occurrence_dict = _GetOccurrenceInformation(occurrence)

    # Currently occurrences of the same flake should have the same project and
    # bucket. No need to group by them or display them on the UI.
    occurrences_dict[occurrence.build_configuration.luci_builder].append(
        occurrence_dict)

  return _ToList(occurrences_dict)


def _GetFlakeAnalysesResults(bug_id):
  """Gets flake analyses results for a flaky test.

  Uses bug_id for a flake to query all analyses for this flake, then gets
  culprits if found.

  Args:
    bug_id (int): Bug id of the flake. It should be the same ID to trigger the
      flake analyses.

  Returns:
    culprits, sample_analysis (list, dict): A list of culprits information or
    a dict of information for a sample analysis if there is no culprit at all.
  """
  culprits = {}

  # TODO(crbug/894215): Query for culprits directly after we change to file
  # a bug per culprit instead of flake.
  analyses = MasterFlakeAnalysis.query(
      MasterFlakeAnalysis.bug_id == bug_id).fetch()
  if not analyses:
    return [], None

  culprit_urlsafe_keys = set([
      analysis.culprit_urlsafe_key
      for analysis in analyses
      if analysis.culprit_urlsafe_key
  ])

  if culprit_urlsafe_keys:
    # Found culprits.
    for key in culprit_urlsafe_keys:
      culprit = entity_util.GetEntityFromUrlsafeKey(key)
      if not culprit:
        logging.error('Failed to get FlakeCulprit entity from key %s', key)
        continue
      culprits[key] = {
          'revision': culprit.revision,
          'commit_position': culprit.commit_position,
          'culprit_key': key
      }

  if culprits:
    return culprits.values(), None

  # No culprits have been found for this flake.
  # Prior to use a completed analysis as a sample; otherwise a running one;
  # otherwise a pending analysis; failed analysis will not be used.
  sample_analysis = {}
  for analysis in analyses:
    if analysis.status == analysis_status.COMPLETED:
      # A completed analysis found, returns immediately.
      return [], {
          'status': ('%s, no culprit found' %
                     analysis_status.STATUS_TO_DESCRIPTION[analysis.status]),
          'analysis_key':
              analysis.key.urlsafe()
      }

    if analysis.status == analysis_status.RUNNING:
      sample_analysis = {
          'status': analysis_status.RUNNING,
          'analysis_key': analysis.key.urlsafe()
      }
    elif not sample_analysis and analysis.status == analysis_status.PENDING:
      sample_analysis = {
          'status': analysis_status.PENDING,
          'analysis_key': analysis.key.urlsafe()
      }

  if sample_analysis:
    sample_analysis['status'] = analysis_status.STATUS_TO_DESCRIPTION[
        sample_analysis['status']]
  return [], sample_analysis


def _FetchFlakeOccurrences(flake, flake_type, max_occurrence_count):
  """Fetches flake occurrences of a certain type.

  Args:
    flake(Flake): Flake object for a flaky test.
    flake_type(FlakeType): Type of the occurrences.
    max_occurrence_count(int): Maximum number of occurrences to fetch.

  Returns:
    (list): A list of occurrences.
  """
  occurrences_query = FlakeOccurrence.query(ancestor=flake.key).filter(
      FlakeOccurrence.flake_type == flake_type).order(
          -FlakeOccurrence.time_happened)

  if max_occurrence_count:
    return occurrences_query.fetch(max_occurrence_count)
  return occurrences_query.fetch()


def GetFlakeInformation(flake, max_occurrence_count, with_occurrences=True):
  """Gets information for a detected flakes.
  Gets occurrences of the flake and the attached monorail issue.

  Args:
    flake(Flake): Flake object for a flaky test.
    max_occurrence_count(int): Maximum number of occurrences to fetch.
    with_occurrences(bool): If the flake must be with occurrences or not.
      For flakes reported by Flake detection, there should always be
      occurrences, but it's not always true for flakes reported by
      Flake Analyzer, ignore those flakes for now.
  Returns:
    flake_dict(dict): A dict of information for the test. Including data from
    its Flake entity, its flake issue information and information of all its
    flake occurrences.
  """
  occurrences = []
  for flake_type in [FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH]:
    typed_occurrences = _FetchFlakeOccurrences(flake, flake_type,
                                               max_occurrence_count)
    occurrences.extend(typed_occurrences)

    if max_occurrence_count:
      max_occurrence_count = max_occurrence_count - len(typed_occurrences)
      if max_occurrence_count == 0:
        # Bails out if the number of occurrences with higher impact has hit the
        # cap.
        break

  if not occurrences and with_occurrences:
    # Flake must be with occurrences, but there is no occurrence, bail out.
    return None

  # Makes sure occurrences are sorted by time_happened in descending order,
  # regardless of types.
  occurrences.sort(key=lambda x: x.time_happened, reverse=True)
  flake_dict = flake.to_dict()
  flake_dict['occurrences'] = _GetGroupedOccurrencesByBuilder(occurrences)

  if flake.flake_issue_key:
    flake_issue = flake.flake_issue_key.get()
    flake_dict['flake_issue'] = flake_issue.to_dict()
    flake_dict['flake_issue']['issue_link'] = FlakeIssue.GetLinkForIssue(
        flake_issue.monorail_project, flake_issue.issue_id)

    flake_dict['culprits'], flake_dict['sample_analysis'] = (
        _GetFlakeAnalysesResults(flake_issue.issue_id))
  return flake_dict
