# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import calendar
import base64
import copy
from datetime import datetime
from datetime import time
from datetime import timedelta
import json
from urllib import quote

from google.appengine.api import users
import webapp2

from testing_utils import testing

from handlers.crash import triage_analysis
from libs import analysis_status
from libs import time_util
from model import result_status
from model import triage_status
from model.crash.fracas_crash_analysis import FracasCrashAnalysis


class TriageAnalysisTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [('/triage-analysis',
        triage_analysis.TriageAnalysis)], debug=True)

  def setUp(self):
    super(TriageAnalysisTest, self).setUp()
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

    self.key = analysis.key
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

  def testTriageAnalysisHandler(self):
    response = self.test_app.post('/triage-analysis?key=%s' %
                                  self.key.urlsafe())
    self.assertEqual(200, response.status_int)

  def testUpdateResultProperty(self):
    updates = [
        {
            'culprit_regression_range': ['1', '2'],
            'regression_range_triage_status': triage_status.TRIAGED_CORRECT
        },
        {
            'culprit_cls': ['https://chromium/src/+/346'],
            'suspected_cls_triage_status': triage_status.TRIAGED_CORRECT
        },
        {
            'culprit_project': 'chromium-v8',
            'suspected_project_triage_status': triage_status.TRIAGED_INCORRECT
        },
        {
            'culprit_components': ['Blink>API'],
            'suspected_components_triage_status': triage_status.TRIAGED_UNSURE
        },
    ]
    for update in updates:

      self.test_app.post('/triage-analysis?key=%s' % self.key.urlsafe(),
                         {'update-data': json.dumps(update)})
      analysis = self.key.get()
      for key, value in update.iteritems():
        self.assertEqual(getattr(analysis, key), value)

  def testUpdateNote(self):
    update = {'note': 'this is a note. +2314>?'}
    self.test_app.post('/triage-analysis?key=%s' % self.key.urlsafe(),
                       {'update-data': json.dumps(update)})
    analysis = self.key.get()
    self.assertEqual(analysis.note, update['note'])
