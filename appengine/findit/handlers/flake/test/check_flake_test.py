# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from handlers.flake import check_flake
from waterfall.test import wf_testcase


class CheckFlakeTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/waterfall/check-flake', check_flake.CheckFlake),
  ], debug=True)

  def testBasicFlow(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = '123'
    step_name = 's'
    test_name = 't'

    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    response = self.test_app.get('/waterfall/check-flake', params={
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'step_name': step_name,
        'test_name': test_name})
    self.assertEquals(200, response.status_int)
