# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from testing_utils import testing

from handlers import try_job_result
from waterfall import buildbot


class TryJobResultTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/try-job-result', try_job_result.TryJobResult),], debug=True)

  def setUp(self):
    super(TryJobResultTest, self).setUp()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 121
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)


  def testTryJobResultHandler(self):
    build_url = buildbot.CreateBuildUrl(
        self.master_name, self.builder_name, self.build_number)
    response = self.test_app.get('/try-job-result', params={'url': build_url})
    expected_results = {}

    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_results, response.json_body)
