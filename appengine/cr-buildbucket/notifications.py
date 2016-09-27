# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from google.appengine.api import taskqueue
from google.appengine.ext import ndb
import webapp2

from components import decorators
from components import pubsub

import model


@ndb.tasklet
def enqueue_callback_task_if_needed_async(build):
  assert ndb.in_transaction()
  assert build
  if not build.pubsub_callback:  # pragma: no cover
    return

  payload = json.dumps({
    'topic': build.pubsub_callback.topic,
    'message': {
      'build_id': build.key.id(),
      'user_data': build.pubsub_callback.user_data,
    },
    'attrs': {
      'build_id': str(build.key.id()),
      'auth_token': build.pubsub_callback.auth_token,
    },
  })
  task = taskqueue.Task(
      url='/internal/task/buildbucket/notify/%d' % build.key.id(),
      payload=payload,
      retry_options=taskqueue.TaskRetryOptions(
          task_age_limit=model.BUILD_TIMEOUT.total_seconds()))
  yield taskqueue.Queue('backend-default').add_async(task, transactional=True)


def enqueue_callback_task_if_needed(build):
  return enqueue_callback_task_if_needed_async(build).get_result()


class TaskPublishNotification(webapp2.RequestHandler):  # pragma: no cover
  """Publishes a PubSub message."""

  @decorators.require_taskqueue('backend-default')
  def post(self, build_id):  # pylint: disable=unused-argument
    body = json.loads(self.request.body)
    pubsub.publish(
        body['topic'],
        json.dumps(body['message'], sort_keys=True),
        body['attrs'])


# This function is left for a short period of time because
# this code used deferred module before.
# TODO(nodir): remove.
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
