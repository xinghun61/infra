# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue

_DEFAULT_PAGE_SIZE = 100
_DEFAULT_LUCI_PROJECT = 'chromium'


class RankFlakes(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    luci_project = self.request.get(
        'luci_project').strip() or _DEFAULT_LUCI_PROJECT

    flake_query = Flake.query(Flake.luci_project == luci_project).filter(
        Flake.false_rejection_count_last_week > 0).order(
            -Flake.false_rejection_count_last_week)

    cursor = None
    more = True
    flakes_data = []
    while more:
      flakes, cursor, more = flake_query.fetch_page(
          _DEFAULT_PAGE_SIZE, start_cursor=cursor)

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
        'flakes_data': flakes_data,
        'luci_project': (luci_project if luci_project != _DEFAULT_LUCI_PROJECT
                         else '')}
    return {'template': 'flake/detection/rank_flakes.html', 'data': data}
