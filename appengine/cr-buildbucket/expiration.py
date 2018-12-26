# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file implements various time-based expiration.

This includes:
- expiration of leases
- expiration of builds after a hard timeout
"""

import datetime

from google.appengine.ext import ndb

import webapp2

from components import decorators
from components import utils

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

    assert build.status != model.BuildStatus.COMPLETED, (
        'Completed build is leased'
    )
    build.clear_lease()
    build.status = model.BuildStatus.SCHEDULED
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

  expected_statuses = (model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED)

  @ndb.transactional_tasklet
  def txn_async(build_key):
    now = utils.utcnow()
    build = yield build_key.get_async()
    if not build or build.status not in expected_statuses:
      raise ndb.Return(False, build)  # pragma: no cover

    build.clear_lease()
    build.status = model.BuildStatus.COMPLETED
    build.complete_time = now
    build.status_changed_time = now
    build.result = model.BuildResult.CANCELED
    build.cancelation_reason = model.CancelationReason.TIMEOUT
    yield build.put_async(), events.on_build_completing_async(build)
    raise ndb.Return(True, build)

  @ndb.tasklet
  def update_async(build_key):
    # This is the only yield in this function, but it is not
    # performance-critical.
    updated, build = yield txn_async(build_key)
    if updated:  # pragma: no branch
      events.on_build_completed(build)

  too_long_ago = utils.utcnow() - model.BUILD_TIMEOUT
  q = model.Build.query(
      model.Build.create_time < too_long_ago,
      # Cannot use >1 inequality filters per query.
      model.Build.status.IN(expected_statuses),
  )
  q.map_async(update_async, keys_only=True).get_result()
