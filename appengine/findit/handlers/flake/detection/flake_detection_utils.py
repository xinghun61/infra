# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Util functions for flake detection handlers."""

from collections import defaultdict
import logging

from google.appengine.ext import ndb

from gae_libs import dashboard_util
from libs import time_util
from libs import analysis_status
from model import entity_util
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import Flake
from model.flake.flake import TAG_DELIMITER
from model.flake.flake_issue import FlakeIssue
from model.flake.flake_type import FlakeType
from model.flake.flake_type import FLAKE_TYPE_DESCRIPTIONS
from services import constants
from services.flake_detection.detect_flake_occurrences import SUPPORTED_TAGS
from services.flake_failure.flake_bug_util import (
    GetMinimumConfidenceToUpdateEndpoints)
from services.flake_issue_util import GetFlakeIssue
from services.issue_constants import OPEN_STATUSES

DEFAULT_PAGE_SIZE = 100
_TEST_FILTER_NAME = 'test'


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

  # Only shows culprits if they have high enough confidence.
  culprit_urlsafe_keys = set([
      analysis.culprit_urlsafe_key
      for analysis in analyses
      if analysis.culprit_urlsafe_key and analysis.confidence_in_culprit and
      analysis.confidence_in_culprit >= GetMinimumConfidenceToUpdateEndpoints()
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
  """Fetches flake occurrences of a certain type within a time range.

  Args:
    flake(Flake): Flake object for a flaky test.
    flake_type(FlakeType): Type of the occurrences.
    max_occurrence_count(int): Maximum number of occurrences to fetch.

  Returns:
    (list): A list of occurrences.
  """
  start_date = time_util.GetDateDaysBeforeNow(days=constants.DAYS_IN_A_WEEK)
  occurrences_query = FlakeOccurrence.query(ancestor=flake.key).filter(
      ndb.AND(FlakeOccurrence.flake_type == flake_type,
              FlakeOccurrence.time_happened >
              start_date)).order(-FlakeOccurrence.time_happened)

  return occurrences_query.fetch(max_occurrence_count)


def _GetLastUpdatedTimeDelta(flake_issue):
  """Uses the latest update time we can get as last_updated_time_in_monorail."""
  last_updated_time = flake_issue.last_updated_time_in_monorail or None
  return (time_util.FormatTimedelta(
      time_util.GetUTCNow() - last_updated_time, with_days=True)
          if last_updated_time else None)


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
  if (max_occurrence_count and not flake.archived and
      flake.flake_score_last_week > 0):
    # On-going flakes, queries the ones in the past-week.
    for flake_type in [
        FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH,
        FlakeType.CI_FAILED_STEP, FlakeType.CQ_HIDDEN_FLAKE
    ]:
      occurrences.extend(
          _FetchFlakeOccurrences(flake, flake_type,
                                 max_occurrence_count - len(occurrences)))
      if len(occurrences) >= max_occurrence_count:
        # Bails out if the number of occurrences with higher impact has hit
        # the cap.
        break

    # Makes sure occurrences are sorted by time_happened in descending order,
    # regardless of types.
    occurrences.sort(key=lambda x: x.time_happened, reverse=True)

  # Falls back to query all recent occurrences.
  occurrences = occurrences or FlakeOccurrence.query(ancestor=flake.key).order(
      -FlakeOccurrence.time_happened).fetch(max_occurrence_count)

  if not occurrences and with_occurrences:
    # Flake must be with occurrences, but there is no occurrence, bail out.
    return None

  flake_dict = flake.to_dict()
  flake_dict['occurrences'] = _GetGroupedOccurrencesByBuilder(occurrences)
  flake_dict['flake_counts_last_week'] = _GetFlakeCountsList(
      flake.flake_counts_last_week)

  flake_issue = GetFlakeIssue(flake)
  if flake_issue and flake_issue.status and flake_issue.status in OPEN_STATUSES:
    flake_dict['flake_issue'] = flake_issue.to_dict()
    flake_dict['flake_issue']['issue_link'] = FlakeIssue.GetLinkForIssue(
        flake_issue.monorail_project, flake_issue.issue_id)
    flake_dict['flake_issue'][
        'last_updated_time_in_monorail'] = _GetLastUpdatedTimeDelta(flake_issue)

    flake_dict['culprits'], flake_dict['sample_analysis'] = (
        _GetFlakeAnalysesResults(flake_issue.issue_id))
  return flake_dict


def GetFlakesByFilter(flake_filter,
                      luci_project,
                      cursor,
                      direction,
                      page_size=None):  # pragma: no cover.
  """Gets flakes by the given filter, then sorts them by the flake score.

  Args:
    flake_filter (str): It could be a test name, or a tag-based filter in the
      following forms:
      * tag::value
      * tag1::value1@tag2::value2
      * tag1::value1@-tag2:value2
    luci_project (str): The Luci project that the flakes are for.
    cursor (None or str): The cursor provides a cursor in the current query
      results, allowing you to retrieve the next set based on the offset.
    direction (str): Either previous or next.
    page_size (int): Limit of results required in one page.

  Returns:
    (flakes, prev_cursor, cursor, grouping_search, error_message)
    flakes (list): A list of Flakes filtered by tags.
    prev_cursor (str): The urlsafe encoding of the cursor, which is at the
      top position of entities of the current page.
    cursor (str): The urlsafe encoding of the cursor, which is at the
      bottom position of entities of the current page.
    grouping_search (bool): Whether it is a group searching.
    error_message (str): An error message if there is one; otherwise None.
  """
  logging.info('Searching filter: %s', flake_filter)

  flakes = []
  error_message = None

  grouping_search = True
  filters = [f.strip() for f in flake_filter.split('@') if f.strip()]

  # The resulted flakes are those:
  # * Match all of positive filters
  # * Not match any of negative filters
  positive_filters = []
  negative_filters = []
  invalid_filters = []
  for f in filters:
    parts = [p.strip() for p in f.split(TAG_DELIMITER)]
    if len(parts) != 2 or not parts[1]:
      invalid_filters.append(f)
      continue

    if parts[0] == _TEST_FILTER_NAME:
      # Search for a specific test.
      grouping_search = False
      flakes = Flake.query(Flake.normalized_test_name == Flake
                           .NormalizeTestName(parts[1])).filter(
                               Flake.luci_project == luci_project).fetch()
      return flakes, '', '', grouping_search, error_message

    negative = False
    if parts[0][0] == '-':
      parts[0] = parts[0][1:]
      negative = True

    if parts[0] not in SUPPORTED_TAGS:
      invalid_filters.append(f)
      continue

    if negative:
      negative_filters.append(TAG_DELIMITER.join(parts))
    else:
      positive_filters.append(TAG_DELIMITER.join(parts))

  if invalid_filters:
    error_message = 'Unsupported tag filters: %s' % ', '.join(invalid_filters)
    return flakes, '', '', grouping_search, error_message

  if not positive_filters:
    # At least one positive filter should be given.
    error_message = 'At least one positive filter required'
    return flakes, '', '', grouping_search, error_message

  logging.info('Positive filters: %r', positive_filters)
  logging.info('Negative filters: %r', negative_filters)

  query = Flake.query(
      ndb.AND(Flake.luci_project == luci_project, Flake.archived == False))  # pylint: disable=singleton-comparison
  for tag in positive_filters:
    query = query.filter(Flake.tags == tag)
  query = query.filter(Flake.flake_score_last_week > 0)
  minimum_flake_count_in_page = max(
      1, page_size / 2) if page_size else DEFAULT_PAGE_SIZE / 2

  while True:
    results, prev_cursor, cursor = dashboard_util.GetPagedResults(
        query,
        order_properties=[
            (Flake.flake_score_last_week, dashboard_util.DESC),
            (Flake.last_occurred_time, dashboard_util.DESC),
            (Flake.normalized_step_name, dashboard_util.ASC),
            (Flake.test_label_name, dashboard_util.ASC),
        ],
        cursor=cursor,
        direction=direction,
        page_size=page_size or DEFAULT_PAGE_SIZE)

    for result in results:
      if negative_filters and any(t in result.tags for t in negative_filters):
        continue
      flakes.append(result)

    if ((direction == dashboard_util.PREVIOUS and prev_cursor == '') or
        cursor == '' or len(flakes) >= minimum_flake_count_in_page):
      # No more results or gets enough flakes on a page.
      # Ideally we expect the page shows the same amount of flakes as the
      # page_size suggests, but in the case with negative_filters, the number of
      # flakes left after filtering out negative_filters is unknown.
      # Uses minimum_flake_count_in_page to cap the flake count in one page from
      # 0.5 page_size to 1.5 page_size.
      break

  return flakes, prev_cursor, cursor, grouping_search, error_message


def _GetFlakeCountsList(flake_counts_last_week):
  """Gets flake counts for all flake types, even if there's no
    occurrences for some of the types.

  Args:
    flake_counts_last_week(list): A list of FlakeCountsByType.
  """
  flake_counts_last_week_dict = {}
  for flake_type, type_desc in FLAKE_TYPE_DESCRIPTIONS.iteritems():
    flake_counts_last_week_dict[flake_type] = {
        'flake_type': type_desc,
        'impacted_cl_count': 0,
        'occurrence_count': 0
    }

  for flake_count in flake_counts_last_week:
    flake_counts_last_week_dict[flake_count.flake_type][
        'impacted_cl_count'] = flake_count.impacted_cl_count
    flake_counts_last_week_dict[flake_count.flake_type][
        'occurrence_count'] = flake_count.occurrence_count

  return [
      flake_counts_last_week_dict[flake_type]
      for flake_type in sorted(FLAKE_TYPE_DESCRIPTIONS)
  ]


def GenerateFlakesData(flakes, include_closed_bug=False):
  """Processes flakes data to make them ready to be displayed on pages.

  Args:
    flakes ([Flake]): A list of Flake objects.
    include_closed_bug (bool): True to include info about closed bugs. Otherwise
      False.

  Returns:
    [dict]: A list of dicts containing each flake's data.
  """
  flakes_data = []
  for flake in flakes:
    flake_dict = flake.to_dict()

    # Tries to use merge_destination first, then falls back to the bug that
    # directly associates to the flake.
    flake_issue = GetFlakeIssue(flake)
    if (flake_issue and
        (include_closed_bug or
         (flake_issue.status and
          flake_issue.status in OPEN_STATUSES))):  # pragma: no branch.
      # Only show open bugs on dashboard.
      # Unless told otherwise.
      flake_dict['flake_issue'] = flake_issue.to_dict()
      flake_dict['flake_issue']['issue_link'] = FlakeIssue.GetLinkForIssue(
          flake_issue.monorail_project, flake_issue.issue_id)
      flake_dict['flake_issue'][
          'last_updated_time_in_monorail'] = _GetLastUpdatedTimeDelta(
              flake_issue)

    flake_dict['flake_urlsafe_key'] = flake.key.urlsafe()
    flake_dict['time_delta'] = time_util.FormatTimedelta(
        time_util.GetUTCNow() - flake.last_occurred_time,
        with_days=True) if flake.last_occurred_time else None

    flake_dict['flake_counts_last_week'] = _GetFlakeCountsList(
        flake.flake_counts_last_week)

    flakes_data.append(flake_dict)
  return flakes_data
