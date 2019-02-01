# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file implements various time-based expiration.

This includes:
- expiration of leases
- expiration of builds after a hard timeout
- deletion of very old builds
"""

import datetime
import logging

from google.appengine.ext import ndb

import webapp2

from components import decorators
from components import utils

from proto import common_pb2
import events
import model


class CronExpireBuildLeases(webapp2.RequestHandler):  # pragma: no cover

  @decorators.require_cronjob
  def get(self):
    expire_build_leases()


def expire_build_leases():
  """Finds builds with expired lease and resets their lease and status."""

  @ndb.transactional_tasklet
  def txn_async(build_key):
    now = utils.utcnow()
    build = yield build_key.get_async()
    if not build or not build.is_leased:  # pragma: no cover
      raise ndb.Return(False, build)

    is_expired = build.lease_expiration_date <= now
    if not is_expired:  # pragma: no cover
      raise ndb.Return(False, build)

    assert not build.is_ended, 'Completed build is leased'
    build.clear_lease()
    build.proto.status = common_pb2.SCHEDULED
    build.status_changed_time = now
    build.url = None
    yield build.put_async(), events.on_build_resetting_async(build)
    raise ndb.Return(True, build)

  @ndb.tasklet
  def update_async(build_key):
    # This is the only yield in this function, but it is not
    # performance-critical.
    updated, build = yield txn_async(build_key)
    if updated:  # pragma: no branch
      events.on_expired_build_reset(build)

  q = model.Build.query(
      model.Build.is_leased == True,
      model.Build.lease_expiration_date <= datetime.datetime.utcnow(),
  )
  q.map_async(update_async, keys_only=True).get_result()


class CronExpireBuilds(webapp2.RequestHandler):  # pragma: no cover

  @decorators.require_cronjob
  def get(self):
    expire_builds()


@ndb.tasklet
def expire_builds():
  """Finds old incomplete builds and marks them as TIMEOUT."""

  expected_statuses = (common_pb2.SCHEDULED, common_pb2.STARTED)

  @ndb.transactional_tasklet
  def txn_async(build_key):
    now = utils.utcnow()
    build = yield build_key.get_async()
    if not build or build.status_v2 not in expected_statuses:
      raise ndb.Return(False, build)  # pragma: no cover

    build.clear_lease()
    build.proto.status = common_pb2.INFRA_FAILURE
    build.proto.infra_failure_reason.resource_exhaustion = True
    build.proto.end_time.FromDatetime(now)
    build.status_changed_time = now
    yield build.put_async(), events.on_build_completing_async(build)
    raise ndb.Return(True, build)

  @ndb.tasklet
  def update_async(build_key):
    # This is the only yield in this function, but it is not
    # performance-critical.
    updated, build = yield txn_async(build_key)
    if updated:  # pragma: no branch
      events.on_build_completed(build)

  # Utilize time-based build keys.
  id_low, _ = model.build_id_range(None, utils.utcnow() - model.BUILD_TIMEOUT)
  q = model.Build.query(
      model.Build.key > ndb.Key(model.Build, id_low),
      # Cannot use >1 inequality filters per query.
      model.Build.status_v2.IN(expected_statuses),
  )
  q.map_async(update_async, keys_only=True).get_result()


class CronDeleteBuilds(webapp2.RequestHandler):  # pragma: no cover

  @decorators.require_cronjob
  def get(self):
    delete_builds()


@ndb.tasklet
def delete_builds():
  """Finds very old builds and deletes them and their children.

  Very old is defined by model.BUILD_STORAGE_DURATION.
  """

  @ndb.transactional_tasklet
  def txn_async(build_key):
    to_delete = [build_key]
    for clazz in model.BUILD_CHILD_CLASSES:
      keys = yield clazz.query(ancestor=build_key).fetch_async(keys_only=True)
      to_delete.extend(keys)
    yield ndb.delete_multi_async(to_delete)

  # Utilize time-based build keys.
  id_low, _ = model.build_id_range(
      None,
      utils.utcnow() - model.BUILD_STORAGE_DURATION
  )
  q = model.Build.query(model.Build.key > ndb.Key(model.Build, id_low))
  nones = q.map_async(txn_async, keys_only=True, limit=1000).get_result()
  logging.info('Deleted %d builds', len(nones))
