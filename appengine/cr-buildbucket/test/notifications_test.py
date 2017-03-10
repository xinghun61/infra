# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os

from google.appengine.ext import deferred
from google.appengine.ext import ndb
from google.appengine.ext import testbed

from testing_utils import testing
import mock

import model
import notifications


BUILDBUCKET_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class NotificationsTest(testing.AppengineTestCase):
  taskqueue_stub_root_path = BUILDBUCKET_ROOT

  @mock.patch('google.appengine.ext.deferred.defer', autospec=True)
  def test_enqueue_callback_task_if_needed(self, _defer):
    build = model.Build(
      id=1,
      bucket='chromium',
      pubsub_callback=model.PubSubCallback(
        topic='projects/example/topic/buildbucket',
        user_data='hello',
        auth_token='secret',
      ),
    )

    @ndb.transactional
    def txn():
      build.put()
      notifications.enqueue_callback_task_if_needed(build)
    txn()

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url='/internal/task/buildbucket/notify/1')
    self.assertEqual(len(tasks), 1)
    task = tasks[0]

    payload = json.loads(task.payload)
    self.assertEqual(payload, {
      'topic': 'projects/example/topic/buildbucket',
      'message': {
        'build_id': 1,
        'user_data': 'hello',
      },
      'attrs': {
        'build_id': '1',
        'auth_token': 'secret',
      },
    })
