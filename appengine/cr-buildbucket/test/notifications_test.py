# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import deferred
from google.appengine.ext import ndb

from testing_utils import testing
import mock

import model
import notifications


class NotificationsTest(testing.AppengineTestCase):
  @ndb.transactional
  def test_enqueue_callback_task_if_needed(self):
    self.mock(deferred, 'defer', mock.Mock())
    build = model.Build(
      bucket='chromium',
      pubsub_callback=model.PubSubCallback(
        topic='projects/example/topic/buildbucket',
        user_data='hello',
        auth_token='secret',
      ),
    )
    build.put()
    notifications.enqueue_callback_task_if_needed(build)
    deferred.defer.assert_called_with(
      notifications._publish_pubsub_message,
      build.key.id(),
      'projects/example/topic/buildbucket',
      'hello',
      'secret',
      _transactional=True,
      _retry_options=mock.ANY,
    )
