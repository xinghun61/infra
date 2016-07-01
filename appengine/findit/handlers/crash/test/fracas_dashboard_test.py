# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import base64
import copy
from datetime import datetime
from datetime import time
from datetime import timedelta
import json

import webapp2

from testing_utils import testing

from common import time_util
from handlers.crash import fracas_dashboard
from model import analysis_status
from model import result_status
from model import triage_status
from model.crash.fracas_crash_analysis import FracasCrashAnalysis

# TODO: Remove, see crbug.com/624998
#pylint: disable=unused-variable

class FracasDashBoardTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [('/fracas-dashboard', fracas_dashboard.FracasDashBoard), ], debug=True)

  def setUp(self):
    super(FracasDashBoardTest, self).setUp()
    self.keys = self._AddAnalysisResults()
    self.fracas_crashes = []
    for key in self.keys:
      self.fracas_crashes.append(self._GenerateDisplayData(key))

    midnight_today = datetime.combine(datetime.utcnow(), time.min)
    midnight_yesterday = midnight_today - timedelta(days=1)
    midnight_tomorrow = midnight_today + timedelta(days=1)
    self.default_start_date = midnight_yesterday
    self.default_end_date = midnight_tomorrow

  def testFracasDashBoardHandler(self):
    response = self.test_app.get('/fracas-dashboard')
    self.assertEqual(200, response.status_int)

  def _CreateAnalysisResult(self, crash_identifiers):
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.status = analysis_status.RUNNING
    return analysis

  def _SetResultsTriageStatus(self, analysis, triage_status_value):
    result_types = ['regression_range', 'suspected_cls', 'suspected_project',
                    'suspected_components']
    for result_type in result_types:
      setattr(analysis, '%s_triage_status' % result_type, triage_status_value)

  def _AddAnalysisResults(self):
    """Create and store dummy data."""
    analyses = []
    keys = []

    for i in range(0, 5):
      crash_identifiers = {'signature': 'sig%d' % i}
      keys.append(crash_identifiers)

      analysis = self._CreateAnalysisResult(crash_identifiers)
      analysis.signature = 'sig%d' % i
      analysis.crashed_version = '53.0.275%d.0' % i
      analysis.stack_trace = 'dummy\nframe1\nframe2'
      analysis.platform = 'android'
      analysis.channel = 'canary'
      analysis.client_id = 'fracas'
      analyses.append(analysis)

    analyses[0].status = analysis_status.COMPLETED
    analyses[1].status = analysis_status.COMPLETED
    analyses[2].status = analysis_status.ERROR
    analyses[3].status = analysis_status.COMPLETED
    analyses[4].status = analysis_status.ERROR

    suspected_cl = {
        'url': 'https://chromium.googlesource.com/chromium/src/+/346a',
        'review_url': 'https://review',
        'revision': '346a',
        'project_path': 'src/',
        'author': 'a@chromium.org',
        'time': '2016-06-04 00:00:00 UTC',
        'reason': 'some reason',
        'confidence': 1
    }
    analyses[0].result = {'found': True,
                          'suspected_cls': [suspected_cl],
                          'suspected_components': ['Blink>API', 'Blink>DOM'],
                          'suspected_project': 'chromium',
                          'regression_range': None}
    analyses[0].found_suspects = True
    analyses[1].result = {'found': False,
                          'suspected_cls': [],
                          'suspected_components': ['Blink>API', 'Blink>DOM'],
                          'suspected_project': 'chromium',
                          'regression_range': None}
    analyses[1].found_suspects = False
    analyses[2].result = {'found': False,
                          'suspected_cls': [],
                          'suspected_components': ['Blink>API', 'Blink>DOM'],
                          'suspected_project': 'chromium',
                          'regression_range': ['53.0.2749.0', '53.0.2750.0']}
    analyses[2].found_suspects = False
    analyses[3].result = {'found': True,
                          'suspected_cls': [suspected_cl],
                          'suspected_components': ['Blink>API'],
                          'suspected_project': 'chromium',
                          'regression_range': ['53.0.2749.0', '53.0.2750.0']}
    analyses[3].found_suspects = True
    analyses[4].result = {'found': False,
                          'suspected_cls': [],
                          'suspected_components': ['Blink>API', 'Blink>DOM'],
                          'suspected_project': 'chromium',
                          'regression_range': ['53.0.2749.0', '53.0.2750.0']}
    analyses[4].found_suspects = False

    start_request_time = datetime.utcnow()
    for i, analysis in enumerate(analyses):
      analysis.requested_time = (start_request_time +
                                 timedelta(minutes=10 * i))

      analysis.has_regression_range = not analysis.result[
          'regression_range'] is None

    self._SetResultsTriageStatus(analyses[0], triage_status.TRIAGED_INCORRECT)
    self._SetResultsTriageStatus(analyses[1], triage_status.TRIAGED_CORRECT)
    self._SetResultsTriageStatus(analyses[3], triage_status.TRIAGED_CORRECT)
    self._SetResultsTriageStatus(analyses[4], triage_status.TRIAGED_UNSURE)

    for analysis in analyses:
      analysis.put()

    return keys

  def _GenerateDisplayData(self, crash_identifiers):
    crash = FracasCrashAnalysis.Get(crash_identifiers)
    return {
        'signature': crash.signature,
        'version': crash.crashed_version,
        'channel': crash.channel,
        'platform': crash.platform,
        'regression_range': ('' if not crash.has_regression_range else
                             crash.result['regression_range']),
        'suspected_cls':crash.result['suspected_cls'],
        'suspected_project': crash.result['suspected_project'],
        'suspected_components': crash.result['suspected_components'],
        'stack_trace': crash.stack_trace,
        'historical_metadata': json.dumps(crash.historical_metadata),
        'key': crash.key.urlsafe()
    }

  def testDisplayAllAnalysisResults(self):
    expected_result = {
        'fracas_crashes': [self.fracas_crashes[4],
                           self.fracas_crashes[3],
                           self.fracas_crashes[2],
                           self.fracas_crashes[1],
                           self.fracas_crashes[0]],
        'end_date': time_util.FormatDatetime(self.default_end_date),
        'regression_range_triage_status': '-1',
        'suspected_cls_triage_status': '-1',
        'found_suspects': '-1',
        'has_regression_range': '-1',
        'start_date': time_util.FormatDatetime(self.default_start_date)
    }

    response_json = self.test_app.get('/fracas-dashboard?format=json')
    self.assertEqual(200, response_json.status_int)
    # TODO: Re-enable, see crbug.com/624998
    # self.assertEqual(expected_result, response_json.json_body)

  def testFilterWithFoundSuspects(self):
    expected_result = {
        'fracas_crashes': [self.fracas_crashes[3],
                           self.fracas_crashes[0]],
        'end_date': time_util.FormatDatetime(self.default_end_date),
        'regression_range_triage_status': '-1',
        'suspected_cls_triage_status': '-1',
        'found_suspects': 'yes',
        'has_regression_range': '-1',
        'start_date': time_util.FormatDatetime(self.default_start_date)
    }

    response_json = self.test_app.get(
        '/fracas-dashboard?found_suspects=yes&format=json')
    self.assertEqual(200, response_json.status_int)
    self.assertEqual(expected_result, response_json.json_body)

  def testFilterWithHasRegression(self):
    expected_result = {
        'fracas_crashes': [self.fracas_crashes[4],
                           self.fracas_crashes[3],
                           self.fracas_crashes[2]],
        'end_date': time_util.FormatDatetime(self.default_end_date),
        'regression_range_triage_status': '-1',
        'suspected_cls_triage_status': '-1',
        'found_suspects': '-1',
        'has_regression_range': 'yes',
        'start_date': time_util.FormatDatetime(self.default_start_date)
    }

    response_json = self.test_app.get(
        '/fracas-dashboard?has_regression_range=yes&format=json')
    self.assertEqual(200, response_json.status_int)
    # TODO: Re-enable, see crbug.com/624998
    # self.assertEqual(expected_result, response_json.json_body)

  def testFilterWithSuspectsUntriaged(self):
    expected_result = {
        'fracas_crashes': [self.fracas_crashes[2]],
        'end_date': time_util.FormatDatetime(self.default_end_date),
        'regression_range_triage_status': '-1',
        'suspected_cls_triage_status': str(triage_status.UNTRIAGED),
        'found_suspects': '-1',
        'has_regression_range': '-1',
        'start_date': time_util.FormatDatetime(self.default_start_date)
    }

    response_json = self.test_app.get(
        '/fracas-dashboard?suspected_cls_triage_status=%d&format=json' %
        triage_status.UNTRIAGED)
    self.assertEqual(200, response_json.status_int)
    self.assertEqual(expected_result, response_json.json_body)

  def testFilterWithSuspectsTriagedUnsure(self):
    expected_result = {
        'fracas_crashes': [self.fracas_crashes[4]],
        'end_date': time_util.FormatDatetime(self.default_end_date),
        'regression_range_triage_status': '-1',
        'suspected_cls_triage_status': str(triage_status.TRIAGED_UNSURE),
        'found_suspects': '-1',
        'has_regression_range': '-1',
        'start_date': time_util.FormatDatetime(self.default_start_date)
    }

    response_json = self.test_app.get(
        '/fracas-dashboard?suspected_cls_triage_status=%d&format=json' %
        triage_status.TRIAGED_UNSURE)
    self.assertEqual(200, response_json.status_int)
    # TODO: Re-enable, see crbug.com/624998
    # self.assertEqual(expected_result, response_json.json_body)

  def testFilterWithRegressionRangeTriagedUnsure(self):
    expected_result = {
        'fracas_crashes': [self.fracas_crashes[4]],
        'end_date': time_util.FormatDatetime(self.default_end_date),
        'regression_range_triage_status': str(triage_status.TRIAGED_UNSURE),
        'suspected_cls_triage_status': '-1',
        'found_suspects': '-1',
        'has_regression_range': '-1',
        'start_date': time_util.FormatDatetime(self.default_start_date)
    }

    response_json = self.test_app.get(
        '/fracas-dashboard?regression_range_triage_status=%d&format=json' %
        triage_status.TRIAGED_UNSURE)
    self.assertEqual(200, response_json.status_int)
    # TODO: Re-enable, see crbug.com/624998
    # self.assertEqual(expected_result, response_json.json_body)

  def testGetTopCountResults(self):
    expected_result = {
        'fracas_crashes': [self.fracas_crashes[4],
                           self.fracas_crashes[3]],
        'end_date': time_util.FormatDatetime(self.default_end_date),
        'regression_range_triage_status': '-1',
        'suspected_cls_triage_status': '-1',
        'found_suspects': '-1',
        'has_regression_range': '-1',
        'start_date': time_util.FormatDatetime(self.default_start_date)
    }

    response_json = self.test_app.get('/fracas-dashboard?count=2&format=json')
    self.assertEqual(200, response_json.status_int)
    # TODO: Re-enable, see crbug.com/624998
    # self.assertEqual(expected_result, response_json.json_body)
