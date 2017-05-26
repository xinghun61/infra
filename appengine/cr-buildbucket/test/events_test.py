# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json

from google.appengine.ext import ndb

from testing_utils import testing

import api_common
from test import test_util
import events
import model


class NotificationsTest(testing.AppengineTestCase):
  def setUp(self):
    super(NotificationsTest, self).setUp()

    self.patch(
        'events.enqueue_tasks_async',
        autospec=True,
        return_value=test_util.future(None))

    self.patch(
        'google.appengine.api.app_identity.get_default_version_hostname',
        return_value='buildbucket.example.com',
        autospec=True)

    self.patch(
        'components.utils.utcnow', return_value=datetime.datetime(2017, 1, 1))

  def test_pubsub_callback(self):
    build = model.Build(
        id=1,
        bucket='chromium',
        create_time=datetime.datetime(2017, 1, 1),
        pubsub_callback=model.PubSubCallback(
            topic='projects/example/topics/buildbucket',
            user_data='hello',
            auth_token='secret',
        ),
    )

    @ndb.transactional
    def txn():
      build.put()
      events.on_build_completing_async(build).get_result()
    txn()

    build = build.key.get()
    events.enqueue_tasks_async.assert_called_with('backend-default', [
      {
        'url': '/internal/task/buildbucket/notify/1',
        'payload': json.dumps({
          'topic': 'projects/testbed-test/topics/builds',
          'message': {
            'build': api_common.build_to_dict(build),
            'hostname': 'buildbucket.example.com',
          },
          'attrs': {
            'build_id': '1',
          },
        }, sort_keys=True),
        'age_limit_sec': model.BUILD_TIMEOUT.total_seconds(),
      },
      {
        'url': '/internal/task/buildbucket/notify/1',
        'payload': json.dumps({
          'topic': 'projects/example/topics/buildbucket',
          'message': {
            'build': api_common.build_to_dict(build),
            'hostname': 'buildbucket.example.com',
            'user_data': 'hello',
          },
          'attrs': {
            'build_id': '1',
            'auth_token': 'secret',
          },
        }, sort_keys=True),
        'age_limit_sec': model.BUILD_TIMEOUT.total_seconds(),
      },
    ])

  def test_no_pubsub_callback(self):
    build = model.Build(
        id=1,
        bucket='chromium',
        create_time=datetime.datetime(2017, 1, 1),
    )

    @ndb.transactional
    def txn():
      build.put()
      events.on_build_completing_async(build).get_result()
    txn()

    build = build.key.get()
    events.enqueue_tasks_async.assert_called_with('backend-default', [{
      'url': '/internal/task/buildbucket/notify/1',
      'payload': json.dumps({
        'topic': 'projects/testbed-test/topics/builds',
        'message': {
          'build': api_common.build_to_dict(build),
          'hostname': 'buildbucket.example.com',
        },
        'attrs': {
          'build_id': '1',
        },
      }, sort_keys=True),
      'age_limit_sec': model.BUILD_TIMEOUT.total_seconds(),
    }])
