# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
from datetime import datetime
from datetime import timedelta
import json
import mock
import re
import webapp2
import webtest

from google.appengine.api import users

from analysis.crash_report import CrashReport
from analysis.stacktrace import CallStack
from analysis.stacktrace import StackFrame
from analysis.stacktrace import Stacktrace
from backend.handlers.update_inverted_index import UpdateInvertedIndex
from backend.handlers.update_inverted_index import UpdateInvertedIndexForCrash
from common.model.fracas_crash_analysis import FracasCrashAnalysis
from common.model.inverted_index import ChromeCrashInvertedIndex
from frontend.handlers import crash_config
from gae_libs.http.http_client_appengine import HttpClientAppengine
from gae_libs.testcase import TestCase
from libs.http.retry_http_client import RetryHttpClient

def _MockKeywrodExtractor(crash_report):
  return crash_report.signature


class UpdateInvertedIndexTest(TestCase):
  """Tests utility functions and ``UpdateInvertedIndex`` handler."""
  app_module = webapp2.WSGIApplication([
      ('/process/update-inverted-index', UpdateInvertedIndex),
  ], debug=True)

  def testUpdateInvertedIndexForCrash(self):
    crash_report = CrashReport('50.0.1234.0', 'sig', 'win',
                               None, None, None, None)
    keywords = _MockKeywrodExtractor(crash_report)
    UpdateInvertedIndexForCrash(crash_report,
                                _MockKeywrodExtractor,
                                inverted_index_model=ChromeCrashInvertedIndex)

    for keyword in keywords:
      inverted_index = ChromeCrashInvertedIndex.Get(keyword)
      self.assertIsNotNone(inverted_index)
      self.assertEqual(inverted_index.n_of_doc, 1)

  def testUpdateInvetedIndexHandlerWithNoStacktrace(self):
    """Tests ``UpdateInvertedIndex`` handler when there is no stacktraces."""
    crash_analysis1 = FracasCrashAnalysis.Create('sig1')
    crash_analysis1.signature = 'sig1'
    crash_analysis1.requested_time = datetime.utcnow() - timedelta(hours=1)
    crash_analysis1.put()
    crash_analysis2 = FracasCrashAnalysis.Create('sig2')
    crash_analysis2.signature = 'sig2'
    crash_analysis2.requested_time = datetime.utcnow() - timedelta(hours=1)
    crash_analysis2.put()

    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    response = self.test_app.get('/process/update-inverted-index')
    self.assertEqual(response.status_int, 200)
    self.assertEqual(ChromeCrashInvertedIndex.GetRoot().n_of_doc, 2)
    self.assertEqual(ChromeCrashInvertedIndex.query().fetch(), [])

  def testUpdateInvetedIndexHandlerWithStacktraces(self):
    """Tests ``UpdateInvertedIndex`` handler when there are stacktraces."""
    crash_analysis = FracasCrashAnalysis.Create('sig1')
    crash_analysis.identifiers = {'signature': 'sig1'}
    crash_analysis.requested_time = datetime.utcnow() - timedelta(hours=1)

    frames = [
        StackFrame(0, 'src/', 'fun1', 'f1.cc', 'src/f1.cc', [2, 3],
                   'http://repo'),
        StackFrame(0, 'src/', 'fun2', 'f2.cc', 'xx/src/f2.cc', [8, 10],
                   'http://repo'),
        StackFrame(0, 'src/', 'fun3', 'f3.cc', 'y/src/f3.cc', [20, 30],
                   'http://repo')
    ]
    callstack = CallStack(0, frames)

    crash_analysis.stacktrace = Stacktrace([callstack], callstack)
    crash_analysis.put()

    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    response = self.test_app.get('/process/update-inverted-index')
    self.assertEqual(response.status_int, 200)
    self.assertEqual(ChromeCrashInvertedIndex.GetRoot().n_of_doc, 1)
    self.assertEqual(
        ChromeCrashInvertedIndex.Get('src/f1.cc').n_of_doc, 1)
    self.assertEqual(
        ChromeCrashInvertedIndex.Get('src/f2.cc').n_of_doc, 1)
    self.assertEqual(
        ChromeCrashInvertedIndex.Get('src/f3.cc').n_of_doc, 1)
