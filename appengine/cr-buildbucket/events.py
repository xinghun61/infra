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

from google.appengine.api import taskqueue
from google.appengine.ext import ndb
import webapp2

from components import auth
from components import decorators
from components import pubsub

import model
import metrics

# Event functions in this file are marked with `# pragma: no cover` because
# they are called from other modules.

# Mocked in tests.
def enqueue_task_async(
    queue, url, payload, task_age_limit_sec):  # pragma: no cover
  task = taskqueue.Task(
      url=url,
      payload=payload,
      retry_options=taskqueue.TaskRetryOptions(
          task_age_limit=task_age_limit_sec))
  return taskqueue.Queue(queue).add_async(task, transactional=True)


@ndb.tasklet
def _enqueue_callback_task_if_needed_async(build):
  assert ndb.in_transaction()
  assert build
  if not build.pubsub_callback:  # pragma: no cover
    return

  payload = json.dumps({
    'topic': build.pubsub_callback.topic,
    'message': {
      'build_id': str(build.key.id()),
      'user_data': build.pubsub_callback.user_data,
    },
    'attrs': {
      'build_id': str(build.key.id()),
      'auth_token': build.pubsub_callback.auth_token,
    },
  }, sort_keys=True)
  return enqueue_task_async(
      'backend-default',
      '/internal/task/buildbucket/notify/%d' % build.key.id(),
      payload,
      model.BUILD_TIMEOUT.total_seconds())


def on_build_created(build):  # pragma: no cover
  assert not ndb.in_transaction()
  logging.info(
      'Build %s for bucket %s was created by %s',
      build.key.id(), build.bucket, auth.get_current_identity().to_bytes())
  metrics.inc_created_builds(build)


def on_build_starting_async(build):  # pragma: no cover
  return _enqueue_callback_task_if_needed_async(build)


def on_build_started(build):  # pragma: no cover
  assert not ndb.in_transaction()
  logging.info('Build %s was started. URL: %s', build.key.id(), build.url)
  metrics.inc_started_builds(build)


def on_build_completing_async(build):  # pragma: no cover
  return _enqueue_callback_task_if_needed_async(build)


def on_build_completed(build):  # pragma: no cover
  assert not ndb.in_transaction()
  logging.info(
      'Build %s was completed by %s. Status: %s. Result: %s',
      build.key.id(),
      auth.get_current_identity().to_bytes(),
      build.status, build.result)
  metrics.inc_completed_builds(build)


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
  return _enqueue_callback_task_if_needed_async(build)


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
