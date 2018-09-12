# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Util functions for flake detection handlers."""

from collections import defaultdict
from datetime import timedelta

from libs import time_util
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from model.flake.detection.flake_occurrence import (
    CQFalseRejectionFlakeOccurrence)

_DAYS_IN_A_WEEK = 7


def _GetOccurrenceInformation(occurrence):
  """Gets information of one occurrence in a dict.

  Args:
    occurrence(CQFalseRejectionFlakeOccurrence): one flake occurrence.

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
    occurrences(list): A list of CQFalseRejectionFlakeOccurrence objects.

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
  start_time = time_util.GetUTCNow() - timedelta(days=_DAYS_IN_A_WEEK)
  occurrences = CQFalseRejectionFlakeOccurrence.query(
      ancestor=flake.key).filter(
          CQFalseRejectionFlakeOccurrence.time_happened >= start_time).order(
              -CQFalseRejectionFlakeOccurrence.time_happened).fetch(
                  max_occurrence_count)

  if not occurrences and with_occurrences:
    # Flake must be with occurrences, but there is no occurrence, bail out.
    return None

  flake_dict = flake.to_dict()
  flake_dict['occurrences'] = _GetGroupedOccurrencesByBuilder(occurrences)

  if flake.flake_issue_key:
    flake_issue = flake.flake_issue_key.get()
    flake_dict['flake_issue'] = flake_issue.to_dict()
    flake_dict['flake_issue']['issue_link'] = FlakeIssue.GetLinkForIssue(
        flake_issue.monorail_project, flake_issue.issue_id)

  return flake_dict
