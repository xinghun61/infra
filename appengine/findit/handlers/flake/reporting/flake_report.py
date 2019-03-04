# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import time_util
from model.flake.reporting.report import ComponentFlakinessReport
from model.flake.reporting.report import TotalFlakinessReport
from services.constants import DEFAULT_LUCI_PROJECT

# Default number of top n components.
_DEFAULT_TOP_COMPONENT_NUM = 10

_DEFAULT_RANK_BY = 'test_count'

# Uses a list of tuples to ensure sequence of tabs on UI.
_RANK_PROPERTY_TUPLES = [('test_count', ComponentFlakinessReport.test_count),
                         ('bug_count', ComponentFlakinessReport.bug_count),
                         ('new_bug_count',
                          ComponentFlakinessReport.new_bug_count),
                         ('false_rejected_cl_count',
                          ComponentFlakinessReport.false_rejected_cl_count)]


# TODO (crbug.com/923552): Add count as a parameter instead of always use the
# default _DEFAULT_TOP_COMPONENT_NUM.
def _QueryTopComponents(total_report_key):
  """Queries previous week's flake report and return the top n components.

  Returns:
    A list of top n components in the previous week ranked by various criteria.
    [{
      'rank_by': 'rank_by',
      'components': [ComponentFlakinessReport.ToSerializable()]
    }]
  """
  component_report_query = ComponentFlakinessReport.query(
      ancestor=total_report_key)

  top_components = []
  for rank_by, rank_property in _RANK_PROPERTY_TUPLES:
    components = component_report_query.order(-rank_property).fetch(
        _DEFAULT_TOP_COMPONENT_NUM)
    query_result = {
        'rank_by': rank_by,
        'components': [component.ToSerializable() for component in components]
    }

    top_components.append(query_result)
  return top_components


class FlakeReport(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    luci_project = self.request.get(
        'luci_project').strip() or DEFAULT_LUCI_PROJECT
    component = self.request.get('component_filter').strip()

    if component:
      return self.CreateRedirect(
          '/p/chromium/flake-portal/report/component?component=%s' % component)

    report_time = time_util.GetPreviousWeekMonday()

    # The report is a weekly report, though we may generate reports more
    # frequently. Uses the Monday report for the whole week.
    total_flakiness_report = TotalFlakinessReport.Get(report_time, luci_project)

    data = {
        'component':
            component,
        'luci_project': (
            luci_project if luci_project != DEFAULT_LUCI_PROJECT else ''),
    }
    if not total_flakiness_report:
      data['total_report'] = {}
      data['top_components'] = []
    else:
      data['total_report'] = total_flakiness_report.ToSerializable()
      data['top_components'] = _QueryTopComponents(total_flakiness_report.key)

    return {'template': 'flake/report/flake_report.html', 'data': data}
