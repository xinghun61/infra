# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

import webapp2

from handlers import build_ahead
from services import build_ahead as build_ahead_service
from waterfall.test import wf_testcase


class BuildAheadTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/cron/build_ahead', build_ahead.BuildAhead),
  ])

  @mock.patch.object(build_ahead_service, 'BuildCaches')
  def testGet(self, mock_service):
    _ = self.test_app.get(
        '/cron/build_ahead',
        headers={'X-AppEngine-Cron': 'true'},
    )
    mock_service.assert_called_once_with()
