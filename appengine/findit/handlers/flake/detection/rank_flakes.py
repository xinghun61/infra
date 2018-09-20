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
      flake_query = Flake.query(Flake.luci_project == luci_project).filter(
          Flake.false_rejection_count_last_week > 0)
      flakes, prev_cursor, cursor = dashboard_util.GetPagedResults(
          flake_query,
          order_properties=[
            (Flake.false_rejection_count_last_week, dashboard_util.DESC),
            (Flake.last_occurred_time, dashboard_util.DESC),
            (Flake.normalized_step_name, dashboard_util.ASC),
            (Flake.test_label_name, dashboard_util.ASC),
          ],
          cursor=self.request.get('cursor'),
          direction=self.request.get('direction').strip(),
          page_size=page_size)

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
            test_filter
    }
    return {'template': 'flake/detection/rank_flakes.html', 'data': data}
