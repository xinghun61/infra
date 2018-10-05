# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

import webapp2

from libs import time_util
from handlers.flake.reporting import generate_report
from services.flake_reporting import component
from waterfall.test import wf_testcase


class PrepareFlakinessReportTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/cron/generate_flakiness_report',
       generate_report.PrepareFlakinessReport),
  ])

  @mock.patch.object(time_util, 'GetPSTNow')
  @mock.patch.object(component, 'Report')
  def testGet(self, mock_service, mock_date):
    mock_date.return_value = datetime.datetime(2018, 1, 10, 0, 0, 0)
    _ = self.test_app.get(
        '/cron/generate_flakiness_report',
        headers={'X-AppEngine-Cron': 'true'},
    )
    self.assertEqual(mock.call(2018, 1), mock_service.call_args)
