# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json

from google.appengine.ext import ndb

from testing_utils import testing
import mock

import events
import model


class NotificationsTest(testing.AppengineTestCase):
  @mock.patch('events.enqueue_task_async', autospec=True)
  def test_enqueue_callback_task_if_needed(self, enqueue_task_async):
    build = model.Build(
        id=1,
        bucket='chromium',
        create_time=datetime.datetime(2017, 1, 1),
        pubsub_callback=model.PubSubCallback(
            topic='projects/example/topic/buildbucket',
            user_data='hello',
            auth_token='secret',
        ),
    )

    @ndb.transactional
    def txn():
      build.put()
      events.on_build_completing_async(build).get_result()
    txn()

    enqueue_task_async.assert_called_with(
        'backend-default',
        '/internal/task/buildbucket/notify/1',
        json.dumps({
          'topic': 'projects/example/topic/buildbucket',
          'message': {
            'build_id': '1',
            'user_data': 'hello',
          },
          'attrs': {
            'build_id': '1',
            'auth_token': 'secret',
          },
        }, sort_keys=True),
        model.BUILD_TIMEOUT.total_seconds())
