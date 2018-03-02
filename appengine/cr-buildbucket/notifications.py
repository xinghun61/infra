# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""PubSub notifications about builds."""

import json
import logging

from google.appengine.api import app_identity
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
import webapp2

from components import decorators
from components import pubsub

import api_common
import model


# Mocked in tests.
@ndb.tasklet
def enqueue_tasks_async(queue, task_defs):  # pragma: no cover
  tasks = [
    taskqueue.Task(
        url=t['url'],
        payload=t['payload'],
        retry_options=taskqueue.TaskRetryOptions(
            task_age_limit=t['age_limit_sec']))
    for t in task_defs
  ]
  # Cannot just return add_async's return value because it is
  # a non-Future object and does not play nice with `yield fut1, fut2` construct
  yield taskqueue.Queue(queue).add_async(tasks, transactional=True)


def enqueue_notifications_async(build):
  assert ndb.in_transaction()
  assert build

  def mktask(mode):
    return {
      'url': '/internal/task/buildbucket/notify/%d' % build.key.id(),
      'payload': json.dumps({
        'id': build.key.id(),
        'mode': mode,
      }, sort_keys=True),
      'age_limit_sec': model.BUILD_TIMEOUT.total_seconds(),
    }

  task_defs = [mktask('global')]
  if build.pubsub_callback:  # pragma: no branch
    task_defs.append(mktask('callback'))
  return enqueue_tasks_async('backend-default', task_defs)


class TaskPublishNotification(webapp2.RequestHandler):
  """Publishes a PubSub message."""

  @decorators.require_taskqueue('backend-default')
  def post(self, build_id):  # pylint: disable=unused-argument
    body = json.loads(self.request.body)

    assert body.get('mode') in ('global', 'callback')
    build = model.Build.get_by_id(body['id'])
    if not build:  # pragma: no cover
      return

    message = {
      'build': api_common.build_to_dict(build),
      'hostname': app_identity.get_default_version_hostname(),
    }
    attrs = {'build_id': str(build.key.id())}
    if body['mode'] == 'callback':
      topic = build.pubsub_callback.topic
      message['user_data'] = build.pubsub_callback.user_data
      attrs['auth_token'] = build.pubsub_callback.auth_token
    else:
      topic = 'projects/%s/topics/builds' % app_identity.get_application_id()

    pubsub.publish(topic, json.dumps(message, sort_keys=True), attrs)
