# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime

from model.flake.detection.flake_occurrence import (
    CQFalseRejectionFlakeOccurrence)
from model.flake.flake import Flake
from model.flake.reporting.report import ComponentFlakinessReport
from model.flake.reporting.report import TestFlakinessReport
from model.flake.reporting.report import TotalFlakinessReport
from services.flake_reporting import component as component_report
from waterfall.test import wf_testcase


def _PutData(test, component, cl, week, hour):

  flake = Flake.Create(
      normalized_test_name=test,
      luci_project='chromium',
      normalized_step_name='normalized_step_name',
      test_label_name='test_label')

  flake.component = component
  flake.put()

  time_happened = datetime.datetime.strptime('2018-W%d-4' % week, '%Y-W%W-%w')
  time_happened += datetime.timedelta(hours=hour)
  occurrence = CQFalseRejectionFlakeOccurrence.Create(
      build_id=123 + hour,
      step_ui_name='step',
      test_name=test,
      luci_project='chromium',
      luci_bucket='try',
      luci_builder='builder',
      legacy_master_name='master',
      legacy_build_number=42,
      time_happened=time_happened,
      gerrit_cl_id=cl,
      parent_flake_key=flake.key)
  occurrence.put()


class ReportTest(wf_testcase.WaterfallTestCase):

  def testBasicReport(self):
    hits = [
        ('testA', 'ComponentA', 1001, 34, 0),
        ('testB', 'ComponentA', 1002, 35, 1),
        ('testB', 'ComponentA', 1003, 35, 2),
        ('testC', 'ComponentB', 1005, 35, 3),
        ('testD', 'ComponentA', 1005, 35, 4),
        ('testD', 'ComponentA', 1005, 35, 5),
        ('testE', 'ComponentA', 1005, 35, 6),
        ('testF', 'Unknown', 1005, 35, 6),
        ('testG', 'ComponentA', 1007, 36, 7),
    ]
    for occurrence in hits:
      _PutData(*occurrence)

    component_report.Report(2018, 35)
    with self.assertRaises(component_report.ReportExistsException):
      component_report.Report(2018, 35)

    report = TotalFlakinessReport.Get(2018, 35)
    self.assertEqual(report.cq_false_rejection_occurrence_count, 7)
    self.assertEqual(report.cl_count, 3)
    self.assertEqual(report.test_count, 5)

    component_report_A = ComponentFlakinessReport.Get(report.key, 'ComponentA')
    self.assertEqual(component_report_A.cq_false_rejection_occurrence_count, 5)
    self.assertEqual(component_report_A.cl_count, 3)
    self.assertEqual(component_report_A.test_count, 3)

    component_report_unknown = ComponentFlakinessReport.Get(
        report.key, 'Unknown')
    self.assertEqual(
        component_report_unknown.cq_false_rejection_occurrence_count, 1)
    self.assertEqual(component_report_unknown.cl_count, 1)
    self.assertEqual(component_report_unknown.test_count, 1)

    component_test_report_A_B = TestFlakinessReport.Get(component_report_A.key,
                                                        'testB')
    self.assertEqual(
        component_test_report_A_B.cq_false_rejection_occurrence_count, 2)
    self.assertEqual(component_test_report_A_B.cl_count, 2)
