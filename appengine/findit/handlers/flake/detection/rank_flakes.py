# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from gae_libs import dashboard_util
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from handlers.flake.detection import flake_detection_utils
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from model.flake.flake_type import FLAKE_TYPE_DESCRIPTIONS
from model.flake.flake_type import FLAKE_TYPE_WEIGHT
from services.flake_detection.detect_flake_occurrences import SUPPORTED_TAGS

_DEFAULT_LUCI_PROJECT = 'chromium'
_DEFAULT_MONORAIL_PROJECT = 'chromium'

# No need to filter for flake since we have search by test functionality;
# 'gerrit_project' and 'luci_project' are the same for all current flakes,
# no need to filter by them.
_TAGS_NOT_FOR_FILTER = ['flake', 'gerrit_project', 'luci_project']


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

  flakes.sort(key=lambda flake: flake.flake_score_last_week, reverse=True)
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
  flake_query = Flake.query(
      ndb.AND(Flake.luci_project == luci_project, Flake.archived == False))  # pylint: disable=singleton-comparison
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


class RankFlakes(BaseHandler):
  """Queries flakes and ranks them by number of occurrences in descending order.
  """
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    luci_project = self.request.get(
        'luci_project').strip() or _DEFAULT_LUCI_PROJECT
    flake_filter = self.request.get('flake_filter').strip()
    page_size = int(self.request.get('n').strip()) if self.request.get(
        'n') else flake_detection_utils.DEFAULT_PAGE_SIZE
    bug_id = int(self.request.get('bug_id').strip()) if self.request.get(
        'bug_id') else None
    monorail_project = self.request.get('monorail_project').strip(
    ) if self.request.get('monorail_project') else _DEFAULT_MONORAIL_PROJECT
    prev_cursor = ''
    cursor = ''
    error_message = None

    if flake_filter:
      # No paging if search for a test name.
      flakes, prev_cursor, cursor, grouping_search, error_message = (
          flake_detection_utils.GetFlakesByFilter(
              flake_filter, luci_project, self.request.get('cursor'),
              self.request.get('direction').strip(), page_size))

      if len(flakes) == 1 and not grouping_search:
        # Only one flake is retrieved when searching a test by full name,
        # redirects to the flake's page.
        # In the case when searching by test suite name, should not redirect
        # even if only one flake is retrieved.
        flake = flakes[0]
        return self.CreateRedirect(
            '/p/chromium/flake-portal/flakes/occurrences?key=%s' %
            flake.key.urlsafe())
    elif bug_id:
      flakes = _GetFlakesByBug(monorail_project, bug_id)
    else:
      flakes, prev_cursor, cursor = _GetFlakeQueryResults(
          luci_project, self.request.get('cursor'),
          self.request.get('direction').strip(), page_size)

    enabled_flakes = flake_detection_utils.RemoveDisabledFlakes(flakes)

    flakes_data = flake_detection_utils.GenerateFlakesData(
        enabled_flakes, bool(bug_id))

    data = {
        'flakes_data':
            flakes_data,
        'prev_cursor':
            prev_cursor,
        'cursor':
            cursor,
        'n': (page_size
              if page_size != flake_detection_utils.DEFAULT_PAGE_SIZE else ''),
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
        ] for flake_type in sorted(FLAKE_TYPE_DESCRIPTIONS)],
        'filter_names': [
            tag for tag in SUPPORTED_TAGS if tag not in _TAGS_NOT_FOR_FILTER
        ]
    }
    return {'template': 'flake/detection/rank_flakes.html', 'data': data}
