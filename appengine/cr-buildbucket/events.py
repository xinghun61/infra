# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions that must be called when important events happen.

on_something_happening functions must be called in a transaction.
on_something_happened functions must be called after the transaction completed
successfully.
"""

import json
import logging

from google.appengine.api import app_identity
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
import webapp2

from components import auth
from components import decorators
from components import pubsub

import api_common
import model
import metrics

# Event functions in this file are marked with `# pragma: no cover` because
# they are called from other modules.

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
  # Cannot just return the return value of add_async because it is
  # a non-Future object and does not play nice with `yield fut1, fut2` construct
  yield taskqueue.Queue(queue).add_async(tasks, transactional=True)


def _enqueue_pubsub_notifications_async(build):
  assert ndb.in_transaction()
  assert build

  build_dict = api_common.build_to_dict(build)
  task_defs = []

  def prep_task(topic, message=None, attrs=None):
    message = message or {}
    message.update(
        build=build_dict, hostname=app_identity.get_default_version_hostname())
    attrs = attrs or {}
    attrs.update(build_id=str(build.key.id()))
    payload = {
      'topic': topic,
      'message': message,
      'attrs': attrs,
    }
    task_defs.append({
      'url': '/internal/task/buildbucket/notify/%d' % build.key.id(),
      'payload': json.dumps(payload, sort_keys=True),
      'age_limit_sec': model.BUILD_TIMEOUT.total_seconds(),
    })

  prep_task('projects/%s/topics/builds' % app_identity.get_application_id())

  if build.pubsub_callback:  # pragma: no branch
    prep_task(
        topic=build.pubsub_callback.topic,
        message={'user_data': build.pubsub_callback.user_data},
        attrs={'auth_token': build.pubsub_callback.auth_token})

  return enqueue_tasks_async('backend-default', task_defs)


def on_build_created(build):  # pragma: no cover
  assert not ndb.in_transaction()
  logging.info(
      'Build %s for bucket %s was created by %s',
      build.key.id(), build.bucket, auth.get_current_identity().to_bytes())
  metrics.inc_created_builds(build)


def on_build_starting_async(build):  # pragma: no cover
  return _enqueue_pubsub_notifications_async(build)


def on_build_started(build):  # pragma: no cover
  assert not ndb.in_transaction()
  logging.info('Build %s was started. URL: %s', build.key.id(), build.url)
  metrics.inc_started_builds(build)


def on_build_completing_async(build):  # pragma: no cover
  return _enqueue_pubsub_notifications_async(build)


def on_build_completed(build):  # pragma: no cover
  assert not ndb.in_transaction()
  logging.info(
      'Build %s was completed by %s. Status: %s. Result: %s',
      build.key.id(),
      auth.get_current_identity().to_bytes(),
      build.status, build.result)
  metrics.inc_completed_builds(build)
  metrics.add_build_cycle_duration(build)
  if build.start_time:
    metrics.add_build_run_duration(build)


def on_heartbeat_failure(build_id, build, ex):  # pragma: no cover
  # build may be None
  assert not ndb.in_transaction()
  logging.warning('Heartbeat for build %s failed: %s', build_id, ex)
  metrics.inc_heartbeat_failures(build)


def on_build_leased(build):  # pragma: no cover
  assert not ndb.in_transaction()
  metrics.inc_leases(build)


def on_expired_build_reset(build):  # pragma: no cover
  assert not ndb.in_transaction()
  logging.info('Build %s with expired lease was reset', build.key.id())
  metrics.inc_lease_expirations(build)


def on_build_resetting_async(build):  # pragma: no cover
  return _enqueue_pubsub_notifications_async(build)


def on_build_reset(build):  # pragma: no cover
  assert not ndb.in_transaction()
  logging.info(
      'Build %s was reset by %s',
      build.key.id(), auth.get_current_identity().to_bytes())


class TaskPublishNotification(webapp2.RequestHandler):  # pragma: no cover
  """Publishes a PubSub message."""

  @decorators.require_taskqueue('backend-default')
  def post(self, build_id):  # pylint: disable=unused-argument
    body = json.loads(self.request.body)
    pubsub.publish(
        body['topic'],
        json.dumps(body['message'], sort_keys=True),
        body['attrs'])
