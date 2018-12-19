# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import webapp2

from gae_libs.handlers.base_handler import BaseHandler
from handlers.flake import update_open_flake_issues
from services import flake_issue_util
from waterfall.test.wf_testcase import WaterfallTestCase


class UpdateOpenFlakeIssuesTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/auto-action/cron/update-open-flake-issues',
       update_open_flake_issues.UpdateOpenFlakeIssuesCron),
  ],
                                       debug=True)

  def setUp(self):
    super(UpdateOpenFlakeIssuesTest, self).setUp()
    self.url = '/auto-action/cron/update-open-flake-issues'

  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  def testTaskAddedToQueue(self, mocked_is_request_from_appself):
    response = self.test_app.get(self.url)
    self.assertEqual(200, response.status_int)
    response = self.test_app.get(self.url)
    self.assertEqual(200, response.status_int)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        queue_names='auto-action-queue')
    self.assertEqual(2, len(tasks))
    self.assertTrue(mocked_is_request_from_appself.called)


class UpdateOpenFlakeIssuesTaskTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/auto-action/task/update-open-flake-issues',
       update_open_flake_issues.UpdateOpenFlakeIssuesTask),
  ],
                                       debug=True)

  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  @mock.patch.object(flake_issue_util, 'SyncOpenFlakeIssuesWithMonorail')
  def testUpdateOpenFlakeIssuesTask(self, mocked_service,
                                    mocked_is_request_from_appself):
    response = self.test_app.get('/auto-action/task/update-open-flake-issues')
    self.assertEqual(200, response.status_int)
    self.assertTrue(mocked_service.called)
    self.assertTrue(mocked_is_request_from_appself.called)
