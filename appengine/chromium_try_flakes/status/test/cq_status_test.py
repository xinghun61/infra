# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import main
from model.flake import Flake
from testing_utils import testing


class CronHandlersTestCase(testing.AppengineTestCase):
  @property
  def app_module(self):
    return main.app

  taskqueue_stub_root_path = ''

  def test_create_tasks_to_update_issue_tracker(self):
    Flake(name='foo1', count_day=1).put()
    key2 = Flake(name='foo2', count_day=10).put()
    key3 = Flake(name='foo3', count_day=15).put()
    Flake(name='foo4', count_day=5).put()
    key5 = Flake(name='foo5', count_day=200).put()

    path = '/cron/update_issue_tracker'
    response = self.test_app.get(path, headers={'X-AppEngine-Cron': 'true'})
    self.assertEquals(200, response.status_int)

    tasks = self.taskqueue_stub.get_filtered_tasks(queue_names='issue-updates')
    self.assertEquals(len(tasks), 3)
    self.assertEquals(tasks[0].url, '/issues/process/%s' % key2.urlsafe())
    self.assertEquals(tasks[1].url, '/issues/process/%s' % key3.urlsafe())
    self.assertEquals(tasks[2].url, '/issues/process/%s' % key5.urlsafe())
