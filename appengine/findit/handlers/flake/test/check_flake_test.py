# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import re

import webapp2
import webtest

from handlers.flake import check_flake
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model import analysis_status
from model.analysis_status import STATUS_TO_DESCRIPTION
from waterfall.test import wf_testcase


class CheckFlakeTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/waterfall/check-flake', check_flake.CheckFlake),
  ], debug=True)

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

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    data_point = DataPoint()
    data_point.build_number = int(build_number)
    data_point.pass_rate = success_rate
    analysis.data_points.append(data_point)
    analysis.status = analysis_status.COMPLETED
    analysis.suspected_flake_build_number = 100
    analysis.request_time = datetime.datetime(2016, 10, 01, 12, 10, 00)
    analysis.start_time = datetime.datetime(2016, 10, 01, 12, 10, 05)
    analysis.end_time = datetime.datetime(2016, 10, 01, 13, 10, 00)
    analysis.algorithm_parameters = {'iterations_to_rerun': 100}
    analysis.Save()

    response = self.test_app.get('/waterfall/check-flake', params={
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'step_name': step_name,
        'test_name': test_name,
        'format': 'json'})

    expected_check_flake_result = {
        'pass_rates': [[int(build_number), success_rate]],
        'analysis_status': STATUS_TO_DESCRIPTION.get(analysis.status),
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': int(build_number),
        'step_name': step_name,
        'test_name': test_name,
        'request_time': '2016-10-01 12:10:00 UTC',
        'task_number': 1,
        'error': None,
        'iterations_to_rerun': 100,
        'pending_time': '00:00:05',
        'duration': '00:59:55',
        'suspected_flake_build_number': 100,
    }

    self.assertEquals(200, response.status_int)
    self.assertEqual(expected_check_flake_result, response.json_body)
