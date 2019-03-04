# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
import mock
import webapp2

from handlers.flake.reporting import flake_report
from libs import time_util
from services.flake_reporting.component import SaveReportToDatastore
from waterfall.test import wf_testcase


class FlakeReportTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/p/chromium/flake-portal/report', flake_report.FlakeReport),
  ],
                                       debug=True)

  def setUp(self):
    super(FlakeReportTest, self).setUp()
    SaveReportToDatastore(wf_testcase.SAMPLE_FLAKE_REPORT_DATA,
                          datetime(2018, 8, 27))

  @mock.patch.object(
      time_util, 'GetPreviousWeekMonday', return_value=datetime(2018, 1, 2))
  def testNoReport(self, _):
    response = self.test_app.get(
        '/p/chromium/flake-portal/report?component=component',
        params={
            'format': 'json',
        },
        status=200)

    self.assertEqual({
        'total_report': {},
        'top_components': [],
        'component': '',
        'luci_project': ''
    }, json.loads(response.body))

  @mock.patch.object(
      time_util, 'GetPreviousWeekMonday', return_value=datetime(2018, 8, 27))
  def testReportWithTopComponents(self, _):
    response = self.test_app.get(
        '/p/chromium/flake-portal/report',
        params={
            'format': 'json',
        },
        status=200)

    component_a_dict = {
        'id': 'ComponentA',
        'test_count': 4,
        'bug_count': 3,
        'new_bug_count': 0,
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

    component_b_dict = {
        'id': 'ComponentB',
        'test_count': 7,
        'bug_count': 1,
        'new_bug_count': 0,
        'impacted_cl_counts': {
            'cq_false_rejection': 2,
            'retry_with_patch': 0,
            'total': 2
        },
        'occurrence_counts': {
            'cq_false_rejection': 1,
            'retry_with_patch': 0,
            'total': 1
        }
    }

    component_unknown_dict = {
        'id': 'Unknown',
        'test_count': 1,
        'bug_count': 6,
        'new_bug_count': 0,
        'impacted_cl_counts': {
            'cq_false_rejection': 1,
            'retry_with_patch': 0,
            'total': 1
        },
        'occurrence_counts': {
            'cq_false_rejection': 1,
            'retry_with_patch': 0,
            'total': 1
        }
    }

    expected_reports = {
        'total_report': {
            'id': '2018-08-27@chromium',
            'test_count': 6,
            'bug_count': 4,
            'new_bug_count': 0,
            'impacted_cl_counts': {
                'cq_false_rejection': 3,
                'retry_with_patch': 0,
                'total': 3
            },
            'occurrence_counts': {
                'cq_false_rejection': 7,
                'retry_with_patch': 1,
                'total': 8
            }
        },
        'top_components': [{
            'rank_by':
                'test_count',
            'components': [
                component_b_dict, component_a_dict, component_unknown_dict
            ]
        },
                           {
                               'rank_by':
                                   'bug_count',
                               'components': [
                                   component_unknown_dict, component_a_dict,
                                   component_b_dict
                               ]
                           },
                           {
                               'rank_by':
                                   'false_rejected_cl_count',
                               'components': [
                                   component_a_dict, component_b_dict,
                                   component_unknown_dict
                               ]
                           },
                           {
                               'rank_by':
                                   'new_bug_count',
                               'components': [
                                   component_a_dict, component_b_dict,
                                   component_unknown_dict
                               ]
                           }],
        'component':
            '',
        'luci_project':
            ''
    }

    response_body_data = json.loads(response.body)

    self.assertEqual(expected_reports['total_report'],
                     response_body_data['total_report'])

    self.assertItemsEqual(expected_reports['top_components'],
                          response_body_data['top_components'])

  def testSearchRedirect(self):
    response = self.test_app.get(
        '/p/chromium/flake-portal/report?component_filter=ComponentA',
        params={
            'format': 'json',
        },
        status=302)

    expected_url_suffix = (
        '/p/chromium/flake-portal/report/component?component=ComponentA')

    self.assertTrue(
        response.headers.get('Location', '').endswith(expected_url_suffix))
