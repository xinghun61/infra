# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs import dashboard_util
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue

_DEFAULT_PAGE_SIZE = 100
_DEFAULT_LUCI_PROJECT = 'chromium'
_MIN_IMPACTED_CLS_WEEKLY = 3


def _GetFlakesByTestFilter(test_name, luci_project):
  """Gets flakes by test name, then sorts them by occurrences."""
  test_suite_search = False
  flakes = Flake.query(Flake.normalized_test_name == Flake.NormalizeTestName(
      test_name)).filter(Flake.luci_project == luci_project).fetch()

  if not flakes:
    # It's possible that the test_name is actually test suite.
    flakes = Flake.query(Flake.test_suite_name == test_name).filter(
        Flake.luci_project == luci_project).fetch()
    test_suite_search = True

  flakes = [f for f in flakes if f.false_rejection_count_last_week > 0]
  flakes.sort(
      key=lambda flake: flake.false_rejection_count_last_week, reverse=True)
  return flakes, test_suite_search


def _GetFlakeQueryResults(luci_project, order_by, cursor, direction, page_size):
  """Gets queried results of flakes.

  Args:
    luci_project (str): Luci project of the flakes.
    order_by (str): Indicates the property to perform as the inequality filter
      and the first sort property. Currently supports
      impacted_cl_count_last_week (default) and false_rejection_count_last_week.
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
  if order_by == 'occurrences':
    flake_query = flake_query.filter(Flake.false_rejection_count_last_week > 0)
    first_sort_property = Flake.false_rejection_count_last_week
  else:
    # Orders flakes by impacted_cl_count_last_week by default.
    flake_query = flake_query.filter(
        Flake.impacted_cl_count_last_week >= _MIN_IMPACTED_CLS_WEEKLY)
    first_sort_property = Flake.impacted_cl_count_last_week

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
    test_filter = self.request.get('test_filter').strip()
    page_size = int(self.request.get('n').strip()) if self.request.get(
        'n') else _DEFAULT_PAGE_SIZE
    order_by = self.request.get('order_by').strip()

    if test_filter:
      # No paging if search for a test name.
      flakes, test_suite_search = _GetFlakesByTestFilter(
          test_filter, luci_project)
      prev_cursor = ''
      cursor = ''

      if len(flakes) == 1 and not test_suite_search:
        # Only one flake is retrieved when searching a test by full name,
        # redirects to the flake's page.
        # In the case when searching by test suite name, should not redirect
        # even if only one flake is retrieved.
        flake = flakes[0]
        return self.CreateRedirect(
            '/flake/occurrences?key=%s' % flake.key.urlsafe())

    else:
      flakes, prev_cursor, cursor = _GetFlakeQueryResults(
          luci_project, order_by, self.request.get('cursor'),
          self.request.get('direction').strip(), page_size)

    flakes_data = []
    for flake in flakes:
      flake_dict = flake.to_dict()

      if flake.flake_issue_key:
        flake_issue = flake.flake_issue_key.get()
        flake_dict['flake_issue'] = flake_issue.to_dict()
        flake_dict['flake_issue']['issue_link'] = FlakeIssue.GetLinkForIssue(
            flake_issue.monorail_project, flake_issue.issue_id)

      flake_dict['flake_urlsafe_key'] = flake.key.urlsafe()
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
        'luci_project': (luci_project
                         if luci_project != _DEFAULT_LUCI_PROJECT else ''),
        'test_filter':
            test_filter,
        'order_by':
            order_by
    }
    return {'template': 'flake/detection/rank_flakes.html', 'data': data}
