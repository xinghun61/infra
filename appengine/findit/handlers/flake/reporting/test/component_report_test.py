# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import webapp2

from handlers.flake.reporting import component_report
from services.flake_reporting.component import SaveReportToDatastore
from waterfall.test import wf_testcase


class ComponentReportTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/flake/report/component', component_report.ComponentReport),
  ],
                                       debug=True)

  def testComponentWithNoComponent(self):
    response = self.test_app.get(
        '/flake/report/component', params={
            'format': 'json',
        }, status=404)

    self.assertEqual('component is required to show component flake report.',
                     response.json_body.get('error_message'))

  def testComponentWithNoReportForComponent(self):
    response = self.test_app.get(
        '/flake/report/component?component=component',
        params={
            'format': 'json',
        },
        status=404)

    self.assertEqual('Didn\'t find reports for component component.',
                     response.json_body.get('error_message'))

  def testComponentWithReport(self):
    SaveReportToDatastore(wf_testcase.SAMPLE_FLAKE_REPORT_DATA, 2018, 35, 1)

    flake_report_data_36 = copy.deepcopy(wf_testcase.SAMPLE_FLAKE_REPORT_DATA)
    flake_report_data_36['_id'] = '2018-W36-1'
    SaveReportToDatastore(flake_report_data_36, 2018, 36, 1)

    response = self.test_app.get(
        '/flake/report/component?component=ComponentA',
        params={
            'format': 'json',
        },
        status=200)
    expected_component_reports = {
        'bug_count': 3,
        'test_count': 4,
        'impacted_cl_counts': {
            'cq_false_rejection': 3,
            'retry_with_patch': 0,
            'total': 3
        },
        'occurrence_counts': {
            'cq_false_rejection': 5,
            'retry_with_patch': 1,
            'total': 6
        }
    }

    response_body_data = json.loads(response.body)

    self.assertEqual('ComponentA', response_body_data['component'])

    for report in response_body_data['component_report_json']:
      self.assertEqual(expected_component_reports['test_count'],
                       report['test_count'])
      self.assertEqual(expected_component_reports['bug_count'],
                       report['bug_count'])
      self.assertItemsEqual(expected_component_reports['impacted_cl_counts'],
                            report['impacted_cl_counts'])
      self.assertItemsEqual(expected_component_reports['occurrence_counts'],
                            report['occurrence_counts'])
