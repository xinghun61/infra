# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from testing_utils import testing

from handlers import swarming_task
from waterfall import buildbot

class SwarmingTaskTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/swarming-task', swarming_task.SwarmingTask),], debug=True)

  def setUp(self):
    super(SwarmingTaskTest, self).setUp()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 121

  def testSwarmingTaskHandler(self):
    build_url = buildbot.CreateBuildUrl(
        self.master_name, self.builder_name, self.build_number)
    response = self.test_app.get('/swarming-task', params={'url': build_url})
    expected_results = {}

    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_results, response.json_body)
