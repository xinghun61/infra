# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock
import webapp2

from google.appengine.api import users
from google.appengine.ext import ndb

from analysis.type_enums import CrashClient
from backend.handlers.rerun_analyses import IterateCrashBatches
from backend.handlers.rerun_analyses import RerunAnalyses
from common.appengine_testcase import AppengineTestCase
from common.crash_pipeline import RerunPipeline
from common.model.cracas_crash_analysis import CracasCrashAnalysis
from gae_libs.pipeline_wrapper import pipeline_handlers


_START_DATE = datetime(2017, 6, 1, 0, 0, 0)
_END_DATE = datetime(2017, 6, 15, 0, 0, 0)


class RerunAnalysesTest(AppengineTestCase):
  """Tests utility functions and ``RerunAnalyses`` handler."""
  app_module = webapp2.WSGIApplication([
      ('/process/rerun-analyses', RerunAnalyses),
  ], debug=True)

  def setUp(self):
    super(RerunAnalysesTest, self).setUp()
    self.crash_analyses = [CracasCrashAnalysis.Create({'signature': 'sig1'}),
                           CracasCrashAnalysis.Create({'signature': 'sig2'}),
                           CracasCrashAnalysis.Create({'signature': 'sig3'})]
    self.crash_analyses[0].requested_time = datetime(2017, 6, 1, 2, 0, 0)
    self.crash_analyses[1].requested_time = datetime(2017, 6, 5, 9, 0, 0)
    self.crash_analyses[2].requested_time = datetime(2017, 6, 10, 3, 0, 0)

    ndb.put_multi(self.crash_analyses)

  @mock.patch('gae_libs.iterator.Iterate')
  def testIterateCrashBatches(self, _):
    """Tests ``IterateCrashBatches`` works as expected."""
    count = 0
    for _ in IterateCrashBatches(
        CrashClient.CRACAS, _START_DATE, _END_DATE, batch_size=1):
      count += 1

    self.assertEqual(count, len(self.crash_analyses))

  @mock.patch('common.crash_pipeline.RerunPipeline.start')
  def testHandleGetWhenThereIsNoCrashAnalyses(self, mock_run):
    """Tests that RerunPipeline didn't run if there is no crash analyses."""
    mock_run.return_value = None
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    response = self.test_app.get(
        '/process/rerun-analyses?start_date=2017-05-19&end_date=2017-05-20')
    self.assertEqual(response.status_int, 200)
    self.assertFalse(mock_run.called)

  @mock.patch('backend.handlers.rerun_analyses.IterateCrashBatches')
  @mock.patch('common.crash_pipeline.RerunPipeline.start')
  def testHandleGetWhenThereIsOneCrashAnalyses(self, mock_run, mock_iterate):
    """Tests that RerunPipeline ran once if there is one crash analysis."""
    mock_run.return_value = None
    def MockIterate(*args, **kwargs):  # pylint: disable=W0613
      yield [self.crash_analyses[0].key.urlsafe()]

    mock_iterate.side_effect = MockIterate
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    response = self.test_app.get(
        '/process/rerun-analyses?start_date=2017-06-01&end_date=2017-06-02')
    self.assertEqual(response.status_int, 200)
    self.assertEqual(mock_run.call_count, 1)

  @mock.patch('backend.handlers.rerun_analyses.IterateCrashBatches')
  @mock.patch('common.crash_pipeline.RerunPipeline.start')
  def testHandleGetWhenThereAreMultipleCrashAnalyses(
      self, mock_run, mock_iterate):
    """Tests starting multiple pipelines if there are many analyses to rerun."""
    mock_run.return_value = None
    def MockIterate(*args, **kwargs):  # pylint: disable=W0613
      for crash in self.crash_analyses:
        yield [crash.key.urlsafe()]

    mock_iterate.side_effect = MockIterate
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    response = self.test_app.get(
        '/process/rerun-analyses?start_date=2017-06-01&end_date=2017-06-03')
    self.assertEqual(response.status_int, 200)
    self.assertEqual(mock_run.call_count, len(self.crash_analyses))
