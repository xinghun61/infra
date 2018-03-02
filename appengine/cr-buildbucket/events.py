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

from google.appengine.ext import ndb

from components import auth

import bq
import metrics
import notifications

# Event functions in this file are marked with `# pragma: no cover` because
# they are called from other modules.


def on_build_created(build):  # pragma: no cover
  assert not ndb.in_transaction()
  logging.info(
      'Build %s for bucket %s was created by %s',
      build.key.id(), build.bucket, auth.get_current_identity().to_bytes())
  metrics.inc_created_builds(build)


def on_build_starting_async(build):  # pragma: no cover
  return notifications.enqueue_notifications_async(build)


def on_build_started(build):  # pragma: no cover
  assert not ndb.in_transaction()
  logging.info('Build %s was started. URL: %s', build.key.id(), build.url)
  metrics.inc_started_builds(build)
  if build.start_time is not None:
    metrics.add_build_scheduling_duration(build)


@ndb.tasklet
def on_build_completing_async(build):  # pragma: no cover
  yield (
    notifications.enqueue_notifications_async(build),
    bq.enqueue_bq_export_async(build),
  )


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


def on_heartbeat_failure(build_id, ex):  # pragma: no cover
  assert not ndb.in_transaction()
  logging.warning('Heartbeat for build %s failed: %s', build_id, ex)
  metrics.inc_heartbeat_failures()


def on_build_leased(build):  # pragma: no cover
  assert not ndb.in_transaction()
  metrics.inc_leases(build)


def on_expired_build_reset(build):  # pragma: no cover
  assert not ndb.in_transaction()
  logging.info('Build %s with expired lease was reset', build.key.id())
  metrics.inc_lease_expirations(build)


def on_build_resetting_async(build):  # pragma: no cover
  return notifications.enqueue_notifications_async(build)


def on_build_reset(build):  # pragma: no cover
  assert not ndb.in_transaction()
  logging.info(
      'Build %s was reset by %s',
      build.key.id(), auth.get_current_identity().to_bytes())
