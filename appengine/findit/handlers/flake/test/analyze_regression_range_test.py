# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import webapp2

from google.appengine.api import users

from handlers.flake import analyze_regression_range
from handlers.flake.analyze_regression_range import AnalyzeRegressionRange
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall.test import wf_testcase


class AnalyzeRegressionRangeTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/waterfall/analyze_regression_range', AnalyzeRegressionRange)],
                                       debug=True)

  def testValidateInput(self):
    self.assertTrue(
        analyze_regression_range._ValidateInput('1', '1', '100'))
    self.assertTrue(
        analyze_regression_range._ValidateInput('2', '1', '100'))
    self.assertTrue(
        analyze_regression_range._ValidateInput(None, '1', '100'))
    self.assertTrue(
        analyze_regression_range._ValidateInput('1', None, '100'))
    self.assertFalse(
        analyze_regression_range._ValidateInput(None, None, '100'))
    self.assertFalse(
        analyze_regression_range._ValidateInput('a', '1', '100'))

  def testGetLowerAndUpperBoundCopmmitPositions(self):
    self.assertEqual(
        (0, 0),
        analyze_regression_range._GetLowerAndUpperBoundCommitPositions(0, 0))
    self.assertEqual(
        (0, 0),
        analyze_regression_range._GetLowerAndUpperBoundCommitPositions(None, 0))
    self.assertEqual(
        (0, 0),
        analyze_regression_range._GetLowerAndUpperBoundCommitPositions(0, None))
    self.assertEqual(
        (None, None),
        analyze_regression_range._GetLowerAndUpperBoundCommitPositions(
            None, None))
    self.assertEqual(
        (1, 2),
        analyze_regression_range._GetLowerAndUpperBoundCommitPositions(1, 2))
    self.assertEqual(
        (1, 2),
        analyze_regression_range._GetLowerAndUpperBoundCommitPositions(2, 1))

  @mock.patch.object(users, 'is_current_user_admin', return_value=True)
  def testPost(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.put()

    self.mock_current_user(user_email='test@google.com')

    response = self.test_app.get('/waterfall/analyze_regression_range', params={
        'lower_bound_commit_position': 1,
        'upper_bound_commit_position': 2,
        'iterations_to_rerun': 100,
        'key': analysis.key.urlsafe()
    })

    self.assertEqual(200, response.status_int)
