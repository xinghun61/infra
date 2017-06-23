# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

import webapp2

from handlers import pipeline_errors_dashboard
from model.wf_analysis import WfAnalysis

from testing_utils import testing


class PipelineErrorsDashboardTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/pipeline-errors-dashboard',
           pipeline_errors_dashboard.PipelineErrorsDashboard),
      ],
      debug=True)

  def testGetStartEndDates(self):
    midnight = datetime(2017, 3, 19, 0, 0, 0)
    self.assertEqual(
        (datetime(2017, 3, 18, 0, 0, 0), datetime(2017, 3, 20, 0, 0, 0)),
        pipeline_errors_dashboard._GetStartEndDates(None, None, midnight))
    self.assertEqual((None, datetime(2017, 3, 20, 0, 0, 0)),
                     pipeline_errors_dashboard._GetStartEndDates(
                         None, '2017-03-19', midnight))
    self.assertEqual((datetime(2017, 3, 18, 0, 0, 0), datetime(
        2017, 3, 20, 0, 0, 0)),
                     pipeline_errors_dashboard._GetStartEndDates(
                         '2017-03-18', None, midnight))
    self.assertEqual((datetime(2017, 3, 15, 0, 0, 0), datetime(
        2017, 3, 16, 0, 0, 0)),
                     pipeline_errors_dashboard._GetStartEndDates(
                         '2017-03-15', '2017-03-16', midnight))

  def testGet(self):
    ok_analysis = WfAnalysis.Create('m1', 'b1', 1)
    ok_analysis.build_start_time = datetime(2017, 3, 19, 0, 0, 1)
    ok_analysis.put()

    aborted_analysis = WfAnalysis.Create('m2', 'b2', 2)
    aborted_analysis.build_start_time = datetime(2017, 3, 19, 0, 0, 2)
    aborted_analysis.aborted = True
    aborted_analysis.put()

    expected_aborted_analyses = [{
        'master_name': 'm2',
        'builder_name': 'b2',
        'build_number': 2,
        'analysis_type': 'unknown',
        'build_start_time': '2017-03-19 00:00:02 UTC'
    }]

    expected_response = {
        'start_date': '2017-03-18 00:00:00 UTC',
        'end_date': '2017-03-20 00:00:00 UTC',
        'analyses': expected_aborted_analyses,
    }

    response = self.test_app.get(
        ('/pipeline-errors-dashboard?format=json&start_date=2017-03-18&'
         'end_date=2017-03-20'))
    response_data = response.json_body

    self.assertEqual(response.status_int, 200)
    self.assertEqual(expected_response, response_data)
