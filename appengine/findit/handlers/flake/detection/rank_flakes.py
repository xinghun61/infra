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


def _GetFlakesByTestName(test_name, luci_project):
  """Gets flakes by test name, then sorts them by occurrences."""
  flakes = Flake.query(Flake.normalized_test_name == Flake.NormalizeTestName(
      test_name)).filter(Flake.luci_project == luci_project).fetch()
  flakes.sort(
      key=lambda flake: flake.false_rejection_count_last_week, reverse=True)
  return flakes


class RankFlakes(BaseHandler):
  """Queries flakes and ranks them by number of occurrences in descending order.
  """
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    luci_project = self.request.get(
        'luci_project').strip() or _DEFAULT_LUCI_PROJECT
    test_name = self.request.get('test_name').strip()
    page_size = int(self.request.get('n').strip()) if self.request.get(
        'n') else _DEFAULT_PAGE_SIZE

    if test_name:
      # No paging if search for a test name.
      flakes = _GetFlakesByTestName(test_name, luci_project)
      prev_cursor = ''
      cursor = ''

      if len(flakes) == 1:
        # Only one flake is retrieved, redirects to the flake's page.
        flake = flakes[0]
        return self.CreateRedirect(
            '/flake/occurrences?key=%s' % flake.key.urlsafe())

    else:
      flake_query = Flake.query(Flake.luci_project == luci_project).filter(
          Flake.false_rejection_count_last_week > 0)
      flakes, prev_cursor, cursor = dashboard_util.GetPagedResults(
          flake_query,
          order_properties=[
              Flake.false_rejection_count_last_week, Flake.last_occurred_time
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
        'test_name_filter':
            test_name
    }
    return {'template': 'flake/detection/rank_flakes.html', 'data': data}
