# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json

from components import utils
utils.fix_protobuf_package()

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

import webtest

from components import pubsub
from test import test_util
from testing_utils import testing

from legacy import api_common
from test import test_util
import bbutil
import main
import model
import notifications
import tq


class NotificationsTest(testing.AppengineTestCase):

  def setUp(self):
    super(NotificationsTest, self).setUp()

    self.app = webtest.TestApp(
        main.create_backend_app(), extra_environ={'REMOTE_ADDR': '127.0.0.1'}
    )

    self.patch(
        'tq.enqueue_async', autospec=True, return_value=test_util.future(None)
    )

    self.patch(
        'google.appengine.api.app_identity.get_default_version_hostname',
        return_value='buildbucket.example.com',
        autospec=True
    )

    self.patch(
        'components.utils.utcnow', return_value=datetime.datetime(2017, 1, 1)
    )

    self.patch('components.pubsub.publish', autospec=True)

  def test_pubsub_callback(self):
    build = test_util.build(id=1)
    build.pubsub_callback = model.PubSubCallback(
        topic='projects/example/topics/buildbucket',
        user_data='hello',
        auth_token='secret',
    )

    out_props = model.BuildOutputProperties(
        key=model.BuildOutputProperties.key_for(build.key),
    )
    out_props.serialize(bbutil.dict_to_struct({'a': 'b'}))

    @ndb.transactional
    def txn():
      build.put()
      out_props.put()
      notifications.enqueue_notifications_async(build).get_result()

    txn()

    build = build.key.get()
    global_task_payload = {
        'id': 1,
        'mode': 'global',
    }
    callback_task_payload = {
        'id': 1,
        'mode': 'callback',
    }
    tq.enqueue_async.assert_called_with(
        'backend-default', [
            {
                'url': '/internal/task/buildbucket/notify/1',
                'payload': global_task_payload,
                'retry_options': {
                    'task_age_limit': model.BUILD_TIMEOUT.total_seconds(),
                },
            },
            {
                'url': '/internal/task/buildbucket/notify/1',
                'payload': callback_task_payload,
                'retry_options': {
                    'task_age_limit': model.BUILD_TIMEOUT.total_seconds(),
                },
            },
        ]
    )

    self.app.post_json(
        '/internal/task/buildbucket/notify/1',
        params=global_task_payload,
        headers={'X-AppEngine-QueueName': 'backend-default'}
    )
    pubsub.publish.assert_called_with(
        'projects/testbed-test/topics/builds',
        json.dumps({
            'build': api_common.build_to_dict(build, out_props),
            'hostname': 'buildbucket.example.com',
        },
                   sort_keys=True),
        {'build_id': '1'},
    )

    self.app.post_json(
        '/internal/task/buildbucket/notify/1',
        params=callback_task_payload,
        headers={'X-AppEngine-QueueName': 'backend-default'}
    )
    pubsub.publish.assert_called_with(
        'projects/example/topics/buildbucket',
        json.dumps({
            'build': api_common.build_to_dict(build, out_props),
            'hostname': 'buildbucket.example.com',
            'user_data': 'hello',
        },
                   sort_keys=True),
        {
            'build_id': '1',
            'auth_token': 'secret',
        },
    )

  def test_no_pubsub_callback(self):
    build = test_util.build(id=1)

    @ndb.transactional
    def txn():
      build.put()
      notifications.enqueue_notifications_async(build).get_result()

    txn()

    build = build.key.get()
    global_task_payload = {
        'id': 1,
        'mode': 'global',
    }
    tq.enqueue_async.assert_called_with(
        'backend-default', [
            {
                'url': '/internal/task/buildbucket/notify/1',
                'payload': global_task_payload,
                'retry_options': {
                    'task_age_limit': model.BUILD_TIMEOUT.total_seconds(),
                },
            },
        ]
    )

    self.app.post_json(
        '/internal/task/buildbucket/notify/1',
        params=global_task_payload,
        headers={'X-AppEngine-QueueName': 'backend-default'}
    )
    pubsub.publish.assert_called_with(
        'projects/testbed-test/topics/builds',
        json.dumps({
            'build': api_common.build_to_dict(build, None),
            'hostname': 'buildbucket.example.com',
        },
                   sort_keys=True),
        {'build_id': '1'},
    )
