# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from gae_libs import dashboard_util
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import time_util
from model import entity_util
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from model.flake.flake_type import FLAKE_TYPE_DESCRIPTIONS
from model.flake.flake_type import FLAKE_TYPE_WEIGHT
from services.flake_detection.detect_flake_occurrences import SUPPORTED_TAGS
from services.flake_detection.detect_flake_occurrences import TAG_SEPARATOR
from services.flake_issue_util import GetFlakeIssue

_DEFAULT_PAGE_SIZE = 100
_DEFAULT_LUCI_PROJECT = 'chromium'
_DEFAULT_MONORAIL_PROJECT = 'chromium'


def _GetFlakesByFilter(flake_filter, luci_project):
  """Gets flakes by the given filter, then sorts them by the flake score.

  Args:
    flake_filter (str): It could be a test name, or a tag-based filter in the
      following forms:
      * tag:value
      * tag1:value1@tag2:value2
      * tag1:value1@-tag2:value2
    luci_project (str): The Luci project that the flakes are for.

  Returns:
    (flakes, grouping_search, error_message)
    flakes (list): A list of Flake that are in descending order of flake score.
    grouping_search (bool): Whether it is a group searching.
    error_message (str): An error message if there is one; otherwise None.
  """
  logging.info('Searching filter: %s', flake_filter)

  flakes = []
  grouping_search = False
  error_message = None

  if TAG_SEPARATOR not in flake_filter:
    # Search for a specific test.
    flakes = Flake.query(Flake.normalized_test_name == Flake.NormalizeTestName(
        flake_filter)).filter(Flake.luci_project == luci_project).fetch()
    flakes = [f for f in flakes if f.flake_score_last_week]

    return flakes, grouping_search, error_message

  grouping_search = True
  filters = [f.strip() for f in flake_filter.split('@') if f.strip()]

  # The resulted flakes are those:
  # * Match all of positive filters
  # * Not match any of negative filters
  positive_filters = []
  negative_filters = []
  invalid_filters = []
  for f in filters:
    parts = [p.strip() for p in f.split(TAG_SEPARATOR)]
    if len(parts) != 2 or not parts[1]:
      invalid_filters.append(f)
      continue

    negative = False
    if parts[0][0] == '-':
      parts[0] = parts[0][1:]
      negative = True

    if parts[0] not in SUPPORTED_TAGS:
      invalid_filters.append(f)
      continue

    if negative:
      negative_filters.append(TAG_SEPARATOR.join(parts))
    else:
      positive_filters.append(TAG_SEPARATOR.join(parts))

  if invalid_filters:
    error_message = 'Unsupported tag filters: %s' % ', '.join(invalid_filters)
    return flakes, grouping_search, error_message

  if not positive_filters:
    # At least one positive filter should be given.
    error_message = 'At least one positive filter required'
    return flakes, grouping_search, error_message

  logging.info('Positive filters: %r', positive_filters)
  logging.info('Negative filters: %r', negative_filters)

  query = Flake.query(Flake.luci_project == luci_project)
  for tag in positive_filters:
    query = query.filter(Flake.tags == tag)

  cursor = None
  more = True
  while more:
    results, cursor, more = query.fetch_page(
        _DEFAULT_PAGE_SIZE, start_cursor=cursor)
    print results

    for result in results:
      if not result.flake_score_last_week:
        continue
      if negative_filters and any(t in result.tags for t in negative_filters):
        continue
      flakes.append(result)

  logging.info('Search got %d flakes', len(flakes))
  flakes.sort(key=lambda flake: flake.flake_score_last_week, reverse=True)
  return flakes, grouping_search, error_message


def _GetFlakesByBug(monorail_project, bug_id):
  """Gets flakes link to the same bug.

  Gets flakes directly link to the bug and also flakes link to bugs that are
    merged into this bug.
  """
  flake_issue = FlakeIssue.Get(monorail_project, bug_id)
  assert flake_issue, 'Requested FlakeIssue {} not found.'.format(bug_id)

  all_issue_keys = [flake_issue.key]
  issue_leaves = FlakeIssue.query(
      FlakeIssue.merge_destination_key == flake_issue.key).fetch(keys_only=True)
  all_issue_keys.extend(issue_leaves)

  flakes = []
  for issue_key in all_issue_keys:
    flakes_to_issue = Flake.query(Flake.flake_issue_key == issue_key).fetch()
    flakes.extend(flakes_to_issue)

  flakes = [f for f in flakes if f.false_rejection_count_last_week > 0]
  flakes.sort(
      key=lambda flake: flake.false_rejection_count_last_week, reverse=True)
  return flakes


def _GetFlakeQueryResults(luci_project, cursor, direction, page_size):
  """Gets queried results of flakes.

  Args:
    luci_project (str): Luci project of the flakes.
    cursor (None or str): The cursor provides a cursor in the current query
      results, allowing you to retrieve the next set based on the offset.
    direction (str): Either previous or next.
    page_size (int): Number of entities to show per page.

  Returns:
    A tuple of (flakes, prev_cursor, cursor).
    flakes (list): List of flakes to be displayed at the current page.
    prev_cursor (str): The urlsafe encoding of the cursor, which is at the
      top position of entities of the current page.
    cursor (str): The urlsafe encoding of the cursor, which is at the
      bottom position of entities of the current page.
  """
  flake_query = Flake.query(Flake.luci_project == luci_project)
  # Orders flakes by flake_score_last_week.
  flake_query = flake_query.filter(Flake.flake_score_last_week > 0)
  first_sort_property = Flake.flake_score_last_week

  return dashboard_util.GetPagedResults(
      flake_query,
      order_properties=[
          (first_sort_property, dashboard_util.DESC),
          (Flake.last_occurred_time, dashboard_util.DESC),
          (Flake.normalized_step_name, dashboard_util.ASC),
          (Flake.test_label_name, dashboard_util.ASC),
      ],
      cursor=cursor,
      direction=direction,
      page_size=page_size)


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


class RankFlakes(BaseHandler):
  """Queries flakes and ranks them by number of occurrences in descending order.
  """
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    luci_project = self.request.get(
        'luci_project').strip() or _DEFAULT_LUCI_PROJECT
    flake_filter = self.request.get('flake_filter').strip()
    page_size = int(self.request.get('n').strip()) if self.request.get(
        'n') else _DEFAULT_PAGE_SIZE
    bug_id = int(self.request.get('bug_id').strip()) if self.request.get(
        'bug_id') else None
    monorail_project = self.request.get('monorail_project').strip(
    ) if self.request.get('monorail_project') else _DEFAULT_MONORAIL_PROJECT
    prev_cursor = ''
    cursor = ''
    error_message = None

    if flake_filter:
      # No paging if search for a test name.
      flakes, grouping_search, error_message = _GetFlakesByFilter(
          flake_filter, luci_project)

      if len(flakes) == 1 and not grouping_search:
        # Only one flake is retrieved when searching a test by full name,
        # redirects to the flake's page.
        # In the case when searching by test suite name, should not redirect
        # even if only one flake is retrieved.
        flake = flakes[0]
        return self.CreateRedirect(
            '/flake/occurrences?key=%s' % flake.key.urlsafe())
    elif bug_id:
      flakes = _GetFlakesByBug(monorail_project, bug_id)
    else:
      flakes, prev_cursor, cursor = _GetFlakeQueryResults(
          luci_project, self.request.get('cursor'),
          self.request.get('direction').strip(), page_size)

    flakes_data = []
    for flake in flakes:
      flake_dict = flake.to_dict()

      # Tries to use merge_destination first, then falls back to the bug that
      # directly associates to the flake.
      flake_issue = GetFlakeIssue(flake)
      if flake_issue:  # pragma: no branch.
        flake_dict['flake_issue'] = flake_issue.to_dict()
        flake_dict['flake_issue']['issue_link'] = FlakeIssue.GetLinkForIssue(
            flake_issue.monorail_project, flake_issue.issue_id)

      flake_dict['flake_urlsafe_key'] = flake.key.urlsafe()
      flake_dict['time_delta'] = time_util.FormatTimedelta(
          time_util.GetUTCNow() - flake.last_occurred_time, with_days=True)

      flake_dict['flake_counts_last_week'] = _GetFlakeCountsList(
          flake.flake_counts_last_week)

      flakes_data.append(flake_dict)

    data = {
        'flakes_data':
            flakes_data,
        'prev_cursor':
            prev_cursor,
        'cursor':
            cursor,
        'n':
            page_size if page_size != _DEFAULT_PAGE_SIZE else '',
        'luci_project': (
            luci_project if luci_project != _DEFAULT_LUCI_PROJECT else ''),
        'flake_filter':
            flake_filter,
        'bug_id':
            bug_id or '',
        'monorail_project': (
            luci_project if luci_project != _DEFAULT_MONORAIL_PROJECT else ''),
        'error_message':
            error_message,
        'flake_weights': [[
            FLAKE_TYPE_DESCRIPTIONS[flake_type], FLAKE_TYPE_WEIGHT[flake_type]
        ] for flake_type in sorted(FLAKE_TYPE_DESCRIPTIONS)]
    }
    return {'template': 'flake/detection/rank_flakes.html', 'data': data}
