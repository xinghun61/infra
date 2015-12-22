# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from google.appengine.api import taskqueue
from google.appengine.ext import deferred
from google.appengine.ext import ndb

from components import pubsub

import model

def enqueue_callback_task_if_needed(build):
  assert ndb.in_transaction()
  assert build
  if build.pubsub_callback:  # pragma: no branch
    deferred.defer(
      _publish_pubsub_message,
      build.key.id(),
      build.pubsub_callback.topic,
      build.pubsub_callback.user_data,
      build.pubsub_callback.auth_token,
      _transactional=True,
      _retry_options=taskqueue.TaskRetryOptions(
        task_age_limit=model.BUILD_TIMEOUT.total_seconds()),
    )

def _publish_pubsub_message(
    build_id, topic, user_data, auth_token):  # pragma: no cover
  message = json.dumps({
    'build_id': build_id,
    'user_data': user_data,
  }, sort_keys=True)
  attrs = {
    'build_id': str(build_id),
    'auth_token': auth_token,
  }
  pubsub.publish(topic, message, attrs)
