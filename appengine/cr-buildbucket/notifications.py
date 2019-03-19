# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""PubSub notifications about builds."""

import json

from google.appengine.api import app_identity
from google.appengine.ext import ndb
import webapp2

from components import decorators
from components import pubsub

from legacy import api_common
import model
import tq


def enqueue_notifications_async(build):
  assert ndb.in_transaction()
  assert build

  def mktask(mode):
    return dict(
        url='/internal/task/buildbucket/notify/%d' % build.key.id(),
        payload=dict(id=build.key.id(), mode=mode),
        retry_options=dict(task_age_limit=model.BUILD_TIMEOUT.total_seconds()),
    )

  tasks = [mktask('global')]
  if build.pubsub_callback:  # pragma: no branch
    tasks.append(mktask('callback'))
  return tq.enqueue_async('backend-default', tasks)


class TaskPublishNotification(webapp2.RequestHandler):
  """Publishes a PubSub message."""

  @decorators.require_taskqueue('backend-default')
  def post(self, build_id):  # pylint: disable=unused-argument
    body = json.loads(self.request.body)

    assert body.get('mode') in ('global', 'callback')
    build = model.Build.get_by_id(body['id'])
    if not build:  # pragma: no cover
      return
    out_props = model.BuildOutputProperties.key_for(build.key).get()

    message = {
        'build': api_common.build_to_dict(build, out_props),
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
