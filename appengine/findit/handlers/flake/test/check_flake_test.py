# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

import webapp2
import webtest

from handlers.flake import check_flake
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model import analysis_status
from model.analysis_status import STATUS_TO_DESCRIPTION
from waterfall.test import wf_testcase


class CheckFlakeTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/waterfall/check-flake', check_flake.CheckFlake),
  ], debug=True)

  def _CreateAndSaveMasterFlakeAnalysis(
      self, master_name, builder_name, build_number,
      step_name, test_name, status):
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.status = status
    analysis.put()
    return analysis

  def testCorpUserCanScheduleANewAnalysis(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = '123'
    step_name = 's'
    test_name = 't'

    self.mock_current_user(user_email='test@google.com')

    response = self.test_app.get('/waterfall/check-flake', params={
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'step_name': step_name,
        'test_name': test_name})

    self.assertEquals(200, response.status_int)

  def testNoneCorpUserCanNotScheduleANewAnalysis(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = '123'
    step_name = 's'
    test_name = 't'

    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*401 Unauthorized.*',
                   re.MULTILINE | re.DOTALL),
        self.test_app.get,
        '/waterfall/check-flake',
        params={
            'master_name': master_name,
            'builder_name': builder_name,
            'build_number': build_number,
            'step_name': step_name,
            'test_name': test_name
        })

  def testAnyoneCanViewScheduledAnalysis(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = '123'
    step_name = 's'
    test_name = 't'
    success_rate = .9
    status = analysis_status.PENDING

    master_flake_analysis = self._CreateAndSaveMasterFlakeAnalysis(
        master_name, builder_name, build_number, step_name,
        test_name, status)
    master_flake_analysis.build_numbers.append(int(build_number))
    master_flake_analysis.success_rates.append(success_rate)
    master_flake_analysis.put()

    response = self.test_app.get('/waterfall/check-flake', params={
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'step_name': step_name,
        'test_name': test_name,
        'format': 'json'})

    self.assertEquals(200, response.status_int)
    expected_check_flake_result ={
        'success_rates': [[int(build_number), success_rate]],
        'analysis_status': STATUS_TO_DESCRIPTION.get(
            master_flake_analysis.status),
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': int(build_number),
        'step_name': step_name,
        'test_name': test_name,
        'suspected_flake_build_number': None
    }
    self.assertEqual(expected_check_flake_result, response.json_body)
