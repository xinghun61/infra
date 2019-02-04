# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from model.flake.reporting.report import ComponentFlakinessReport
from model.flake.reporting.report import TestFlakinessReport
from model.flake.reporting.report import TotalFlakinessReport
from services.flake_reporting.component import SaveReportToDatastore
from waterfall.test import wf_testcase


class ReportTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(ReportTest, self).setUp()
    SaveReportToDatastore(
        wf_testcase.SAMPLE_FLAKE_REPORT_DATA,
        datetime(2018, 8, 27),
        save_test_report=True)

  def testReport(self):
    report_time = datetime(2018, 8, 27)
    report = TotalFlakinessReport.Get(report_time, 'chromium')
    self.assertEqual(6, report.test_count)
    self.assertEqual(8, report.GetTotalOccurrenceCount())
    self.assertEqual(3, report.GetTotalCLCount())

    report_data = {
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
    }

    self.assertEqual(report_data, report.ToSerializable())
    self.assertEqual('chromium', report.GetProject())
    self.assertIn('luci_project::chromium', report.tags)

    component_report_A = ComponentFlakinessReport.Get(report.key, 'ComponentA')
    self.assertEqual(4, component_report_A.test_count)
    self.assertEqual(6, component_report_A.GetTotalOccurrenceCount())
    self.assertEqual(3, component_report_A.GetTotalCLCount())
    self.assertEqual(3, component_report_A.false_rejected_cl_count)

    reports_queried_by_component = ComponentFlakinessReport.query(
        ComponentFlakinessReport.tags == 'component::ComponentA').fetch()
    self.assertEqual(component_report_A, reports_queried_by_component[0])

    component_test_report_A_B = TestFlakinessReport.Get(component_report_A.key,
                                                        'testB')
    self.assertEqual(1, component_test_report_A_B.test_count)
    self.assertEqual(2, component_test_report_A_B.GetTotalOccurrenceCount())
    self.assertEqual(2, component_test_report_A_B.GetTotalCLCount())

    reports_queried_by_test = TestFlakinessReport.query(
        TestFlakinessReport.tags == 'test::testB').fetch()
    self.assertEqual(component_test_report_A_B, reports_queried_by_test[0])

  def testGetFalseRejectedCLCount(self):
    report_time = datetime(2018, 8, 27)
    report = TotalFlakinessReport.Get(report_time, 'chromium')
    self.assertEqual(3, report.false_rejected_cl_count)
