# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from datetime import datetime
from datetime import timedelta
import mock

from libs import time_util
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import Flake
from model.flake.flake import FlakeCountsByType
from model.flake.flake_issue import FlakeIssue
from model.flake.flake_type import FlakeType
from model.flake.reporting.report import ComponentFlakinessReport
from model.flake.reporting.report import TestFlakinessReport
from model.flake.reporting.report import TotalFlakinessReport
from services.flake_reporting import component as component_report
from waterfall.test import wf_testcase


def _GetOrCreateFlakeIssue(bug_id):
  monorail_project = 'chromium'
  issue = FlakeIssue.Get(monorail_project, bug_id)
  if issue:
    return issue

  issue = FlakeIssue.Create(monorail_project, bug_id)
  issue.put()
  return issue


def _CreateFlake(flake_data, with_component=True):
  """
  Args:
    with_component (bool): Sets flake.component if True, otherwise sets tags.
  """

  luci_project = 'chromium'
  normalized_step_name = 'normalized_step_name'

  flake_issue = _GetOrCreateFlakeIssue(flake_data['bug_id'])

  flake = Flake.Create(
      normalized_test_name=flake_data['test'],
      luci_project=luci_project,
      normalized_step_name=normalized_step_name,
      test_label_name='test_label')

  if with_component:
    flake.component = flake_data['component']
  else:
    flake.tags = ['component::{}'.format(flake_data['component'])]
  flake.flake_issue_key = flake_issue.key
  flake.flake_counts_last_week = []
  for flake_type, counts in flake_data['counts'].iteritems():
    flake.flake_counts_last_week.append(
        FlakeCountsByType(
            flake_type=flake_type,
            occurrence_count=counts[0],
            impacted_cl_count=counts[1]))
  flake.last_occurred_time = datetime.strptime(flake_data['last_occurred_time'],
                                               '%Y-W%W-%w')
  flake.put()

  for occurrence_data in flake_data['occurrences']:
    time_happened = datetime.strptime('2018-%d-4' % occurrence_data[2],
                                      '%Y-%W-%w')
    hour = occurrence_data[3]
    time_happened += timedelta(hours=hour)
    occurrence = FlakeOccurrence.Create(
        flake_type=occurrence_data[0],
        build_id=123 + hour,
        step_ui_name='step',
        test_name=flake.normalized_test_name,
        luci_project='chromium',
        luci_bucket='try',
        luci_builder='builder',
        legacy_master_name='master',
        legacy_build_number=42,
        time_happened=time_happened,
        gerrit_cl_id=occurrence_data[1],
        parent_flake_key=flake.key)
    occurrence.put()


class ReportTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(ReportTest, self).setUp()
    flakes_data = [
        {
            'test':
                'testA',
            'component':
                'ComponentA',
            'bug_id':
                123456,
            'last_occurred_time':
                '2018-W34-4',
            'counts': {
                FlakeType.CQ_FALSE_REJECTION: (1, 1)
            },
            'occurrences': [
                # flake_type, gerrit_cl_id, week, hour
                (FlakeType.CQ_FALSE_REJECTION, 1001, 34, 0)
            ]
        },
        {
            'test':
                'testB',
            'component':
                'ComponentA',
            'bug_id':
                123457,
            'last_occurred_time':
                '2018-W35-4',
            'counts': {
                FlakeType.CQ_FALSE_REJECTION: (2, 2)
            },
            'occurrences': [(FlakeType.CQ_FALSE_REJECTION, 1002, 35, 1),
                            (FlakeType.CQ_FALSE_REJECTION, 1003, 35, 2)]
        },
        {
            'test': 'testC',
            'component': 'ComponentB',
            'bug_id': 123458,
            'last_occurred_time': '2018-W35-4',
            'counts': {
                FlakeType.CQ_FALSE_REJECTION: (1, 1)
            },
            'occurrences': [(FlakeType.CQ_FALSE_REJECTION, 1005, 35, 3)]
        },
        {
            'test':
                'testD',
            'component':
                'ComponentA',
            'bug_id':
                123457,
            'last_occurred_time':
                '2018-W35-4',
            'counts': {
                FlakeType.CQ_FALSE_REJECTION: (1, 1),
                FlakeType.RETRY_WITH_PATCH: (1, 0)
            },
            'occurrences': [(FlakeType.CQ_FALSE_REJECTION, 1002, 35, 1),
                            (FlakeType.RETRY_WITH_PATCH, 1002, 35, 2)]
        },
        {
            'test': 'testE',
            'component': 'ComponentA',
            'bug_id': 123460,
            'last_occurred_time': '2018-W35-4',
            'counts': {
                FlakeType.CQ_FALSE_REJECTION: (1, 1)
            },
            'occurrences': [(FlakeType.CQ_FALSE_REJECTION, 1005, 35, 6)]
        },
        {
            'test': 'testF',
            'component': 'Unknown',
            'bug_id': 123460,
            'last_occurred_time': '2018-W35-4',
            'counts': {
                FlakeType.CQ_FALSE_REJECTION: (1, 1)
            },
            'occurrences': [(FlakeType.CQ_FALSE_REJECTION, 1005, 35, 6)]
        },
        {
            'test': 'testG',
            'component': 'ComponentA',
            'bug_id': 123470,
            'last_occurred_time': '2018-W35-4',
            'counts': {
                FlakeType.CQ_FALSE_REJECTION: (1, 1)
            },
            'occurrences': [(FlakeType.CQ_FALSE_REJECTION, 1007, 36, 7)]
        }
    ]

    for i in xrange(len(flakes_data)):
      flake_data = flakes_data[i]
      with_component = True if i % 2 else False
      _CreateFlake(flake_data, with_component)

  @mock.patch.object(
      time_util, 'GetDateDaysBeforeNow', return_value=datetime(2018, 8, 27))
  def testBasicReport(self, _):
    report_date = datetime(2018, 8, 27)
    component_report.Report(save_test_report=True)
    with self.assertRaises(component_report.ReportExistsException):
      component_report.Report()

    report = TotalFlakinessReport.Get(report_date, 'chromium')
    self.assertEqual(6, report.test_count)
    self.assertEqual(4, report.bug_count)

    expected_report_counts = {
        FlakeType.CQ_FALSE_REJECTION: (7, 3),
        FlakeType.RETRY_WITH_PATCH: (1, 0),
        FlakeType.CQ_HIDDEN_FLAKE: (0, 0),
        FlakeType.CI_FAILED_STEP: (0, 0)
    }

    for occurrence_count in report.occurrence_counts:
      self.assertEqual(expected_report_counts[occurrence_count.flake_type][0],
                       occurrence_count.count)

    for cl_count in report.impacted_cl_counts:
      self.assertEqual(expected_report_counts[cl_count.flake_type][1],
                       cl_count.count)

    component_report_A = ComponentFlakinessReport.Get(report.key, 'ComponentA')
    self.assertEqual(4, component_report_A.test_count)
    self.assertEqual(3, component_report_A.bug_count)

    expected_A_counts = {
        FlakeType.CQ_FALSE_REJECTION: (5, 3),
        FlakeType.RETRY_WITH_PATCH: (1, 0),
        FlakeType.CQ_HIDDEN_FLAKE: (0, 0),
        FlakeType.CI_FAILED_STEP: (0, 0)
    }

    for occurrence_count in component_report_A.occurrence_counts:
      self.assertEqual(expected_A_counts[occurrence_count.flake_type][0],
                       occurrence_count.count)

    for cl_count in component_report_A.impacted_cl_counts:
      self.assertEqual(expected_A_counts[cl_count.flake_type][1],
                       cl_count.count)

    component_report_unknown = ComponentFlakinessReport.Get(
        report.key, 'Unknown')
    self.assertEqual(1, component_report_unknown.test_count)
    self.assertEqual(1, component_report_unknown.bug_count)

    expected_Unknown_counts = {
        FlakeType.CQ_FALSE_REJECTION: (1, 1),
        FlakeType.RETRY_WITH_PATCH: (0, 0),
        FlakeType.CQ_HIDDEN_FLAKE: (0, 0),
        FlakeType.CI_FAILED_STEP: (0, 0)
    }

    for occurrence_count in component_report_unknown.occurrence_counts:
      self.assertEqual(expected_Unknown_counts[occurrence_count.flake_type][0],
                       occurrence_count.count)

    for cl_count in component_report_unknown.impacted_cl_counts:
      self.assertEqual(expected_Unknown_counts[cl_count.flake_type][1],
                       cl_count.count)

    component_test_report_A_B = TestFlakinessReport.Get(component_report_A.key,
                                                        'testB')
    self.assertEqual(1, component_test_report_A_B.test_count)
    self.assertEqual(1, component_test_report_A_B.bug_count)

    expected_A_B_counts = {
        FlakeType.CQ_FALSE_REJECTION: (2, 2),
        FlakeType.RETRY_WITH_PATCH: (0, 0),
        FlakeType.CQ_HIDDEN_FLAKE: (0, 0),
        FlakeType.CI_FAILED_STEP: (0, 0)
    }

    for occurrence_count in component_test_report_A_B.occurrence_counts:
      self.assertEqual(expected_A_B_counts[occurrence_count.flake_type][0],
                       occurrence_count.count)

    for cl_count in component_test_report_A_B.impacted_cl_counts:
      self.assertEqual(expected_A_B_counts[cl_count.flake_type][1],
                       cl_count.count)

  @mock.patch.object(
      time_util, 'GetDateDaysBeforeNow', return_value=datetime(2018, 8, 27))
  def testBasicReportNoTestReports(self, _):
    report_date = datetime(2018, 8, 27)
    component_report.Report()

    report = TotalFlakinessReport.Get(report_date, 'chromium')
    self.assertEqual(6, report.test_count)
    self.assertEqual(4, report.bug_count)

    expected_report_counts = {
        FlakeType.CQ_FALSE_REJECTION: (7, 3),
        FlakeType.RETRY_WITH_PATCH: (1, 0),
        FlakeType.CQ_HIDDEN_FLAKE: (0, 0),
        FlakeType.CI_FAILED_STEP: (0, 0)
    }

    for occurrence_count in report.occurrence_counts:
      self.assertEqual(expected_report_counts[occurrence_count.flake_type][0],
                       occurrence_count.count)

    for cl_count in report.impacted_cl_counts:
      self.assertEqual(expected_report_counts[cl_count.flake_type][1],
                       cl_count.count)

    component_report_A = ComponentFlakinessReport.Get(report.key, 'ComponentA')
    self.assertEqual(4, component_report_A.test_count)
    self.assertEqual(3, component_report_A.bug_count)

    expected_A_counts = {
        FlakeType.CQ_FALSE_REJECTION: (5, 3),
        FlakeType.RETRY_WITH_PATCH: (1, 0),
        FlakeType.CQ_HIDDEN_FLAKE: (0, 0),
        FlakeType.CI_FAILED_STEP: (0, 0)
    }

    for occurrence_count in component_report_A.occurrence_counts:
      self.assertEqual(expected_A_counts[occurrence_count.flake_type][0],
                       occurrence_count.count)

    for cl_count in component_report_A.impacted_cl_counts:
      self.assertEqual(expected_A_counts[cl_count.flake_type][1],
                       cl_count.count)

    component_report_unknown = ComponentFlakinessReport.Get(
        report.key, 'Unknown')
    self.assertEqual(1, component_report_unknown.test_count)
    self.assertEqual(1, component_report_unknown.bug_count)

    expected_Unknown_counts = {
        FlakeType.CQ_FALSE_REJECTION: (1, 1),
        FlakeType.RETRY_WITH_PATCH: (0, 0),
        FlakeType.CQ_HIDDEN_FLAKE: (0, 0),
        FlakeType.CI_FAILED_STEP: (0, 0)
    }

    for occurrence_count in component_report_unknown.occurrence_counts:
      self.assertEqual(expected_Unknown_counts[occurrence_count.flake_type][0],
                       occurrence_count.count)

    for cl_count in component_report_unknown.impacted_cl_counts:
      self.assertEqual(expected_Unknown_counts[cl_count.flake_type][1],
                       cl_count.count)
