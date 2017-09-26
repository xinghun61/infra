# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import OrderedDict
import mock

from analysis.type_enums import CrashClient
from common.appengine_testcase import AppengineTestCase
from common.model.clusterfuzz_analysis import ClusterfuzzAnalysis
from frontend.handlers import clusterfuzz_dashboard


class ClusterfuzzDashBoardTest(AppengineTestCase):

  def setUp(self):
    super(ClusterfuzzDashBoardTest, self).setUp()
    self.dashboard = clusterfuzz_dashboard.ClusterfuzzDashBoard()

  def testCrashAnalysisCls(self):
    self.assertEqual(self.dashboard.crash_analysis_cls, ClusterfuzzAnalysis)

  def testClient(self):
    self.assertEqual(self.dashboard.client, CrashClient.CLUSTERFUZZ)

  def testTemplate(self):
    self.assertEqual(self.dashboard.template, 'clusterfuzz_dashboard.html')

  def testPropertyToValueConverter(self):
    self.assertListEqual(
        list(self.dashboard.property_to_value_converter),
        ['found_suspects',
        'has_regression_range',
        'suspected_cls_triage_status',
        'regression_range_triage_status',
        'testcase_id'])
    self.assertTrue(self.dashboard.property_to_value_converter[
        'found_suspects']('yes'))
    self.assertTrue(self.dashboard.property_to_value_converter[
        'has_regression_range']('yes'))
    self.assertEqual(self.dashboard.property_to_value_converter[
        'suspected_cls_triage_status']('1'), 1)
    self.assertEqual(self.dashboard.property_to_value_converter[
        'regression_range_triage_status']('2'), 2)
    self.assertEqual(self.dashboard.property_to_value_converter[
        'testcase_id']('123'), '123')

  def testCrashDataToDisplayWhenThereIsNoCrashToDisplay(self):
    self.assertEqual(self.dashboard.CrashDataToDisplay([]), [])

  def testCrashDataToDisplay(self):
    analysis = ClusterfuzzAnalysis()
    analysis.signature = 'sig'
    analysis.testcase_id = '123'
    analysis.crashed_version = '134abs'
    analysis.job_type = 'asan_job'
    analysis.crash_type = 'check'
    analysis.platform = 'win'
    analysis.commit_count_in_regression_range = 3
    analysis.error_name = 'Failed to parse stacktrace'
    analysis.result = {
        'suspected_cls': [{'author': 'someone'}],
        'suspected_project': 'chromium',
        'suspected_components': ['Blink'],
    }
    analysis.put()

    expected_display_data = [{
        'signature': 'sig',
        'testcase_id': '123',
        'version': '134abs',
        'job_type': 'asan_job',
        'crash_type': 'check',
        'platform': 'win',
        'commits': 3,
        'error_name': 'Failed to parse stacktrace',
        'suspected_cls': [{'author': 'someone'}],
        'suspected_project': 'chromium',
        'suspected_components': ['Blink'],
        'key': analysis.key.urlsafe(),
    }]

    self.assertListEqual(self.dashboard.CrashDataToDisplay([analysis]),
                         expected_display_data)
