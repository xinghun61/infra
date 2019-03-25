# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from handlers.flake.detection import flake_detection_utils
from libs import time_util
from model.flake.flake import Flake
from model.flake.reporting.report import ComponentFlakinessReport
from model.flake.reporting.report import TotalFlakinessReport
from services.constants import DEFAULT_LUCI_PROJECT

# Default to show reports for 12 weeks of data.
_DEFAULT_MAX_ROW_NUM = 12
_DEFAULT_TOP_FLAKE_NUM = 10


def _GenerateComponentReportJson(component_reports):
  """Generates component report in json format.

  Args:
    component_reports ([ComponentFlakinessReport])
  """
  component_reports_json = []
  for report in component_reports:
    report_data = report.ToSerializable()

    report_data['report_time'] = time_util.FormatDatetime(
        report.report_time, day_only=True)
    component_reports_json.append(report_data)

  return component_reports_json


def _QueryTotalReports(luci_project, limit=_DEFAULT_MAX_ROW_NUM):
  tags = [
      TotalFlakinessReport.GenerateTag('luci_project', luci_project),
      # Only displays one report per week, though we may generate report more
      # frequently.
      TotalFlakinessReport.GenerateTag('day', 1),
  ]

  query = TotalFlakinessReport.query()

  for tag in tags:
    query = query.filter(TotalFlakinessReport.tags == tag)

  return query.order(-TotalFlakinessReport.report_time).fetch(limit)


def _QueryComponentReports(component, luci_project, limit=_DEFAULT_MAX_ROW_NUM):
  tags = [
      ComponentFlakinessReport.GenerateTag('luci_project', luci_project),
      ComponentFlakinessReport.GenerateTag('component', component),
      # Only displays one report per week, though we may generate report more
      # frequently.
      ComponentFlakinessReport.GenerateTag('day', 1),
  ]

  query = ComponentFlakinessReport.query()

  for tag in tags:
    query = query.filter(ComponentFlakinessReport.tags == tag)

  return query.order(-ComponentFlakinessReport.report_time).fetch(limit)


class ComponentReport(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    total = self.request.get('total').strip()
    component = self.request.get('component').strip()
    luci_project = self.request.get(
        'luci_project').strip() or DEFAULT_LUCI_PROJECT
    if not component and not total:
      return self.CreateError(
          'A component is required to show its flake report, or add total=1 to '
          'show total numbers.',
          return_code=404)

    if component:
      component_reports = _QueryComponentReports(component, luci_project)
      if not component_reports:
        return self.CreateError(
            'Didn\'t find reports for project {}, component {}.'.format(
                luci_project, component),
            return_code=404)
      report_json = _GenerateComponentReportJson(component_reports)
      top_flakes, _, _, _, _ = flake_detection_utils.GetFlakesByFilter(
          ComponentFlakinessReport.GenerateTag('component', component),
          luci_project, cursor=None, direction='next',
          page_size=_DEFAULT_TOP_FLAKE_NUM)

    else:
      total_reports = _QueryTotalReports(luci_project)
      report_json = _GenerateComponentReportJson(total_reports)
      top_flakes = Flake.query().order(-Flake.flake_score_last_week).fetch(
          _DEFAULT_TOP_FLAKE_NUM)

    flakes_data = flake_detection_utils.GenerateFlakesData(top_flakes)

    data = {
        'report_json':
            report_json,
        'component':
            component if component else 'All',
        'top_flakes':
            flakes_data,
        'total':
            total,
        'luci_project': (
            luci_project if luci_project != DEFAULT_LUCI_PROJECT else ''),
    }
    return {'template': 'flake/report/component_report.html', 'data': data}
