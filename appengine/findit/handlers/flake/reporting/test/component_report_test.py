# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import datetime
import json
import mock
import webapp2

from handlers.flake.detection import flake_detection_utils
from handlers.flake.reporting import component_report
from libs import time_util
from model.flake.flake import Flake
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

    self.assertEqual(
        'A component is required to show its flake report, or add'
        ' total=1 to show total numbers.',
        response.json_body.get('error_message'))

  def testComponentWithNoReportForComponent(self):
    response = self.test_app.get(
        '/flake/report/component?component=component',
        params={
            'format': 'json',
        },
        status=404)

    self.assertEqual(
        'Didn\'t find reports for project chromium, component component.',
        response.json_body.get('error_message'))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 10, 2, 1))
  @mock.patch.object(flake_detection_utils, 'GetFlakesByFilter')
  def testComponentWithReport(self, mock_top_flakes, _):
    SaveReportToDatastore(wf_testcase.SAMPLE_FLAKE_REPORT_DATA,
                          datetime.datetime(2018, 8, 27))

    flake_report_data_36 = copy.deepcopy(wf_testcase.SAMPLE_FLAKE_REPORT_DATA)
    flake_report_data_36['chromium']['_id'] = '2018-09-03@chromium'
    SaveReportToDatastore(flake_report_data_36, datetime.datetime(2018, 9, 3))

    flake_counts_last_week = [
        {
            'flake_type': 'cq false rejection',
            'impacted_cl_count': 0,
            'occurrence_count': 0
        },
        {
            'flake_type': 'cq retry with patch',
            'impacted_cl_count': 0,
            'occurrence_count': 0
        },
        {
            'flake_type': 'cq hidden flake',
            'impacted_cl_count': 0,
            'occurrence_count': 0
        },
        {
            'flake_type': 'ci failed step',
            'impacted_cl_count': 0,
            'occurrence_count': 0
        },
    ]

    luci_project = 'chromium'
    normalized_step_name = 's'
    flake1 = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name='suite.test2',
        test_label_name='suite.test2')
    flake1.false_rejection_count_last_week = 5
    flake1.impacted_cl_count_last_week = 3
    flake1.flake_score_last_week = 10800
    flake1.last_occurred_time = datetime.datetime(2018, 10, 1)
    flake1.tags = ['component::ComponentA']
    flake1.put()
    flake1_dict = flake1.to_dict()
    flake1_dict['flake_urlsafe_key'] = flake1.key.urlsafe()
    flake1_dict['flake_counts_last_week'] = flake_counts_last_week
    flake1_dict['time_delta'] = '1 day, 01:00:00'

    flake2 = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name='suite.test3',
        test_label_name='suite.test3')
    flake2.false_rejection_count_last_week = 5
    flake2.impacted_cl_count_last_week = 3
    flake2.flake_score_last_week = 1080
    flake2.last_occurred_time = datetime.datetime(2018, 10, 1)
    flake2.tags = ['component::ComponentA']
    flake2.put()
    flake2_dict = flake2.to_dict()
    flake2_dict['flake_urlsafe_key'] = flake2.key.urlsafe()
    flake2_dict['flake_counts_last_week'] = flake_counts_last_week
    flake2_dict['time_delta'] = '1 day, 01:00:00'

    mock_top_flakes.return_value = ([flake1, flake2], True, None)

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

    expected_flakes = [flake1_dict, flake2_dict]

    response_body_data = json.loads(response.body)

    self.assertEqual('ComponentA', response_body_data['component'])

    for report in response_body_data['report_json']:
      self.assertEqual(expected_component_reports['test_count'],
                       report['test_count'])
      self.assertEqual(expected_component_reports['bug_count'],
                       report['bug_count'])
      self.assertItemsEqual(expected_component_reports['impacted_cl_counts'],
                            report['impacted_cl_counts'])
      self.assertItemsEqual(expected_component_reports['occurrence_counts'],
                            report['occurrence_counts'])

    for i in xrange(len(response_body_data['top_flakes'])):
      self.assertEqual(
          json.dumps(expected_flakes[i], sort_keys=True, default=str),
          json.dumps(response_body_data['top_flakes'][i], sort_keys=True))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 10, 2, 1))
  def testTotalReport(self, _):
    SaveReportToDatastore(wf_testcase.SAMPLE_FLAKE_REPORT_DATA,
                          datetime.datetime(2018, 8, 27))
    response = self.test_app.get(
        '/flake/report/component?total=1',
        params={
            'format': 'json',
        },
        status=200)

    response_body_data = json.loads(response.body)
    self.assertEqual('1', response_body_data['total'])
    self.assertEqual('All', response_body_data['component'])
    self.assertEqual([], response_body_data['top_flakes'])

    expected_report_json = {
        'bug_count': 4,
        'test_count': 6,
        'impacted_cl_counts': {
            'cq_false_rejection': 3,
            'retry_with_patch': 0,
            'total': 3
        },
        'occurrence_counts': {
            'cq_false_rejection': 7,
            'retry_with_patch': 1,
            'total': 8
        },
        'id': '2018-08-27@chromium',
        'report_time': '2018-08-27'
    }

    self.assertEqual(expected_report_json, response_body_data['report_json'][0])
