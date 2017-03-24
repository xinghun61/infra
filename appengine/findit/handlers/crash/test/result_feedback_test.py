# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
from datetime import datetime

from google.appengine.api import users
import webapp2

from crash.stacktrace import CallStack
from crash.stacktrace import StackFrame
from crash.stacktrace import Stacktrace
from handlers.crash import result_feedback
from libs import time_util
from model import analysis_status
from model import triage_status
from model.crash.fracas_crash_analysis import FracasCrashAnalysis
from testing_utils import testing


class MockResultFeedback(result_feedback.ResultFeedback):

  @property
  def client(self):
    return 'MockClient'


class ResultFeedbackTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [('/result-feedback', MockResultFeedback)], debug=True)

  def setUp(self):
    super(ResultFeedbackTest, self).setUp()
    self.handler = MockResultFeedback()
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    analysis = FracasCrashAnalysis.Create({'signature': 'signature'})
    analysis.signature = 'signature'
    analysis.crashed_version = '53.0.2750.0'
    analysis.stack_trace = 'dummy\nframe1\nframe2'
    analysis.platform = 'android'
    analysis.channel = 'canary'
    analysis.status = analysis_status.COMPLETED
    analysis.historical_metadata = [
        {'chrome_version': '53.0.2748.0', 'cpm': 0},
        {'chrome_version': '53.0.2749.0', 'cpm': 0},
        {'chrome_version': '53.0.2750.0', 'cpm': 0.8}
    ]

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

    analysis.result = {'found': True,
                       'suspected_cls': [suspected_cl],
                       'suspected_components': ['Blink>API', 'Blink>DOM'],
                       'suspected_project': 'chromium',
                       'regression_range': ['53.0.2749.0', '53.0.2750.0']}
    analysis.found_suspects = True
    analysis.note = 'This is a note.'
    analysis.put()

    self.analysis = analysis

  def testResultFeedbackHandler(self):
    response = self.test_app.get('/result-feedback?key=%s' %
                                 self.analysis.key.urlsafe())
    self.assertEqual(200, response.status_int)

  def _GenerateDisplayData(self, analysis):
    if analysis.stack_trace:
      stacktrace_str = analysis.stack_trace
    else:
      stack_strs = []
      for stack in analysis.stacktrace.stacks if analysis.stacktrace else []:
        stack_strs.append('\n'.join([str(frame) for frame in stack.frames]))
      stacktrace_str = '\n'.join(stack_strs)

    return {
        'client': self.handler.client,
        'crash_url': '',
        'signature': analysis.signature,
        'version': analysis.crashed_version,
        'channel': analysis.channel,
        'platform': analysis.platform,
        'regression_range': analysis.result.get('regression_range'),
        'culprit_regression_range': analysis.culprit_regression_range,
        'historical_metadata': analysis.historical_metadata,
        'stack_trace': stacktrace_str,
        'suspected_cls': analysis.result.get('suspected_cls'),
        'culprit_cls': analysis.culprit_cls,
        'suspected_project': analysis.result.get('suspected_project'),
        'culprit_project': analysis.culprit_project,
        'suspected_components': analysis.result.get('suspected_components'),
        'culprit_components': analysis.culprit_components,
        'request_time': time_util.FormatDatetime(analysis.requested_time),
        'analysis_completed': analysis.completed,
        'analysis_failed': analysis.failed,
        'triage_history': result_feedback._GetTriageHistory(analysis),
        'analysis_correct': {
            'regression_range': analysis.regression_range_triage_status,
            'suspected_cls': analysis.suspected_cls_triage_status,
            'suspected_project': analysis.suspected_project_triage_status,
            'suspected_components': analysis.suspected_components_triage_status,
        },
        'note': analysis.note,
        'key': analysis.key.urlsafe(),
    }

  def testDisplayAnanlysisResultWithStactraceString(self):
    self.analysis.culprit_cls = [
        'https://chromium.googlesource.com/chromium/src/+/346a']
    expected_result = self._GenerateDisplayData(self.analysis)
    response_json = self.test_app.get('/result-feedback?format=json&'
                                      'key=%s' % self.analysis.key.urlsafe())
    self.assertEqual(200, response_json.status_int)
    self.assertEqual(expected_result, response_json.json_body)

  def testDisplayAnanlysisResultWithParsedStactrace(self):
    analysis = self.analysis
    frame = StackFrame(0, 'src/', 'func', 'file0.cc', 'src/file0.cc', [32])
    stack = CallStack(0, [frame])
    stacktrace = Stacktrace([stack], stack)
    analysis.stacktrace = stacktrace
    analysis.stack_trace = None

    expected_result = self._GenerateDisplayData(analysis)
    response_json = self.test_app.get('/result-feedback?format=json&'
                                      'key=%s' % self.analysis.key.urlsafe())
    self.assertEqual(200, response_json.status_int)
    self.assertEqual(expected_result, response_json.json_body)

  def testDisplayTriageHistory(self):

    def _MockIsCurrectUserAdmin(*_):
      return True

    self.mock(users, 'is_current_user_admin', _MockIsCurrectUserAdmin)

    self.analysis.triage_history = [{
        'triage_timestamp': calendar.timegm(datetime.utcnow().timetuple()),
        'result_property': 'regression_range',
        'user_name': 'test',
        'triage_status': triage_status.TRIAGED_CORRECT
    }]
    self.analysis.put()
    expected_result = self._GenerateDisplayData(self.analysis)
    response_json = self.test_app.get('/result-feedback?format=json&'
                                      'key=%s' % self.analysis.key.urlsafe())
    self.assertEqual(200, response_json.status_int)
    self.assertEqual(expected_result, response_json.json_body)
