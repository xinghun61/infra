# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import time_util
from model.flake.reporting.report import ComponentFlakinessReport
from model.flake.reporting.report import TotalFlakinessReport

# Default number of top n components.
_DEFAULT_TOP_N = 10

_DEFAULT_RANK_BY = 'test_count'

_RANK_PROPERTY_MAP = {
    'test_count': ComponentFlakinessReport.test_count,
    'bug_count': ComponentFlakinessReport.bug_count,
    'false_rejected_cl_count': ComponentFlakinessReport.false_rejected_cl_count
}


def _QueryTopComponents(total_report_key, rank_by):
  """Queries previous week's flake report and return the top n components.

  Returns:
    [ComponentFlakinessReport]: Top n components in the previous week.
  """
  component_report_query = ComponentFlakinessReport.query(
      ancestor=total_report_key)
  return component_report_query.order(-_RANK_PROPERTY_MAP.get(
      rank_by, ComponentFlakinessReport.test_count)).fetch(_DEFAULT_TOP_N)


class FlakeReport(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    rank_by = self.request.get('rank_by').strip() or _DEFAULT_RANK_BY
    component = self.request.get('component_filter').strip()

    data = {
        'rank_by': rank_by if rank_by != _DEFAULT_RANK_BY else '',
        'component': component
    }

    if component:
      print component
      return self.CreateRedirect(
          '/flake/component-report?component=%s' % component)

    year, week, _ = time_util.GetPreviousISOWeek()
    # The report is a weekly report, though we may generate reports more
    # frequently. Uses the Monday report for the whole week.
    total_flakiness_report = TotalFlakinessReport.Get(year, week, 1)

    if not total_flakiness_report:
      data['total_report'] = {}
      data['top_components'] = []
    else:
      data['total_report'] = total_flakiness_report.ToSerializable()
      top_components = _QueryTopComponents(total_flakiness_report.key, rank_by)
      data['top_components'] = [
          component.ToSerializable() for component in top_components
      ]

    return {'template': 'flake/report/flake_report.html', 'data': data}
