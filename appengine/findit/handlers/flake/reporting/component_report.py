# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from handlers.flake.detection import flake_detection_utils
from model.flake.reporting.report import ComponentFlakinessReport
from model.flake.reporting.report import GetReportDateString

# Default to show reports for 12 weeks of data.
_DEFAULT_MAX_ROW_NUM = 12
_DEFAULT_TOP_FLAKE_NUM = 10

_DEFAULT_LUCI_PROJECT = 'chromium'


def _GenerateComponentReportJson(component_reports):
  """Generates component report in json format.

  Args:
    component_reports ([ComponentFlakinessReport])
  """
  component_reports_json = []
  for report in component_reports:
    report_data = report.ToSerializable()

    report_data['report_time'] = GetReportDateString(report)
    component_reports_json.append(report_data)

  return component_reports_json


def _QueryComponentReports(component, limit=_DEFAULT_MAX_ROW_NUM):
  tags = [
      ComponentFlakinessReport.GenerateTag('component', component),
      # Only displays one report per week, though we may generate report more
      # frequently.
      ComponentFlakinessReport.GenerateTag('day', 1),
  ]

  query = ComponentFlakinessReport.query()

  for tag in tags:
    query = query.filter(ComponentFlakinessReport.tags == tag)

  return query.order(-ComponentFlakinessReport.generated_time).fetch(limit)


class ComponentReport(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    component = self.request.get('component').strip()
    luci_project = self.request.get(
        'luci_project').strip() or _DEFAULT_LUCI_PROJECT
    if not component:
      return self.CreateError(
          'component is required to show component flake report.',
          return_code=404)

    component_reports = _QueryComponentReports(component)
    if not component_reports:
      return self.CreateError(
          'Didn\'t find reports for component %s.' % component, return_code=404)

    component_report_json = _GenerateComponentReportJson(component_reports)

    top_flakes, _, _ = flake_detection_utils.GetFlakesByFilter(
        'component::{}'.format(component), luci_project, _DEFAULT_TOP_FLAKE_NUM)

    flakes_data = flake_detection_utils.GenerateFlakesData(top_flakes)

    data = {
        'component_report_json': component_report_json,
        'component': component,
        'top_flakes': flakes_data
    }
    return {'template': 'flake/report/component_report.html', 'data': data}
