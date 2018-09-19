# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import contextlib
import datetime
import logging
import random
import urlparse

from google.appengine.api import taskqueue
from google.appengine.api import modules
from google.appengine.ext import deferred
from google.appengine.ext import ndb

from components import auth
from components import net
from components import utils
import gae_ts_mon

from proto import build_pb2
from proto.config import project_config_pb2
import buildtags
import config
import errors
import events
import model
import search
import sequence
import swarming
import user

MAX_RETURN_BUILDS = 100
DEFAULT_LEASE_DURATION = datetime.timedelta(minutes=1)

validate_bucket_name = errors.validate_bucket_name

# A cumlative counter of access denied errors in peek() method.
# This metric exists because defining it on the buildbucket server is easier
# than modifying Buildbot. It is very specific intentionally.
PEEK_ACCESS_DENIED_ERROR_COUNTER = gae_ts_mon.CounterMetric(
    'buildbucket/peek_access_denied_errors', 'Number of errors in peek API',
    [gae_ts_mon.StringField('bucket')]
)


def validate_lease_key(lease_key):
  if lease_key is None:
    raise errors.InvalidInputError('Lease key is not provided')


def validate_url(url):
  if url is None:
    return
  if not isinstance(url, basestring):
    raise errors.InvalidInputError('url must be string')
  parsed = urlparse.urlparse(url)
  if not parsed.netloc:
    raise errors.InvalidInputError('url must be absolute')
  if parsed.scheme.lower() not in ('http', 'https'):
    raise errors.InvalidInputError(
        'Unexpected url scheme: "%s"' % parsed.scheme
    )


def unregister_builders():
  """Unregisters builders that didn't have builds for 4 weeks."""
  threshold = utils.utcnow() - model.BUILDER_EXPIRATION_DURATION
  q = model.Builder.query(model.Builder.last_scheduled < threshold)
  keys = q.fetch(keys_only=True)
  if keys:  # pragma: no branch
    logging.warning('unregistered builders: %s', [k.id() for k in keys])
    ndb.delete_multi(keys)


@ndb.tasklet
def get_async(build_id):
  """Gets a build by |build_id|.

  Requires the current user to have permissions to view the build.
  """
  build = yield model.Build.get_by_id_async(build_id)
  if not build:
    raise ndb.Return(None)
  if not (yield user.can_view_build_async(build)):
    raise user.current_identity_cannot('view build %s', build.key.id())
  raise ndb.Return(build)


def peek(buckets, max_builds=None, start_cursor=None):
  """Returns builds available for leasing in the specified |buckets|.

  Builds are sorted by creation time, oldest first.

  Args:
    buckets (list of string): fetch only builds in any of |buckets|.
    max_builds (int): maximum number of builds to return. Defaults to 10.
    start_cursor (string): a value of "next" cursor returned by previous
      peek call. If not None, return next builds in the query.

  Returns:
    A tuple:
      builds (list of Builds): available builds.
      next_cursor (str): cursor for the next page.
        None if there are no more builds.
  """
  if not buckets:
    raise errors.InvalidInputError('No buckets specified')
  buckets = sorted(set(buckets))
  search.check_acls_async(
      buckets, inc_metric=PEEK_ACCESS_DENIED_ERROR_COUNTER
  ).get_result()
  max_builds = search.fix_max_builds(max_builds)

  # Prune any buckets that are paused.
  bucket_states = _get_bucket_states(buckets)
  active_buckets = []
  for b in buckets:
    if bucket_states[b].is_paused:
      logging.warning('Ignoring paused bucket: %s.', b)
      continue
    active_buckets.append(b)

  # Short-circuit: if there are no remaining buckets to query, then we're done.
  if not active_buckets:
    return ([], None)

  q = model.Build.query(
      model.Build.status == model.BuildStatus.SCHEDULED,
      model.Build.is_leased == False,
      model.Build.bucket.IN(active_buckets),
  )
  q = q.order(-model.Build.key)  # oldest first.

  # Check once again locally because an ndb query may return an entity not
  # satisfying the query.
  def local_predicate(b):
    return (
        b.status == model.BuildStatus.SCHEDULED and not b.is_leased and
        b.bucket in active_buckets
    )

  return search.fetch_page_async(
      q, max_builds, start_cursor, predicate=local_predicate
  ).get_result()


def _get_leasable_build(build_id):
  build = model.Build.get_by_id(build_id)
  if build is None:
    raise errors.BuildNotFoundError()
  if not user.can_lease_build_async(build).get_result():
    raise user.current_identity_cannot('lease build %s', build.key.id())
  return build


def lease(build_id, lease_expiration_date=None):
  """Leases the build, makes it unavailable for the leasing.

  Changes lease_key to a different value.

  After the lease expires, a cron task will make the build leasable again.

  Args:
    build_id (int): build id.
    lease_expiration_date (datetime.datetime): lease expiration date.
      Defaults to 10 seconds from now.

  Returns:
    Tuple:
      success (bool): True if the build was leased
      build (ndb.Build)
  """
  errors.validate_lease_expiration_date(lease_expiration_date)
  if lease_expiration_date is None:
    lease_expiration_date = utils.utcnow() + DEFAULT_LEASE_DURATION

  @ndb.transactional
  def try_lease():
    build = _get_leasable_build(build_id)

    if build.status != model.BuildStatus.SCHEDULED or build.is_leased:
      return False, build

    build.lease_expiration_date = lease_expiration_date
    build.regenerate_lease_key()
    build.leasee = auth.get_current_identity()
    build.never_leased = False
    build.put()
    return True, build

  updated, build = try_lease()
  if updated:
    events.on_build_leased(build)
  return updated, build


def _check_lease(build, lease_key):
  if lease_key != build.lease_key:
    raise errors.LeaseExpiredError(
        'lease_key for build %s is incorrect. Your lease might be expired.' %
        build.key.id()
    )


def reset(build_id):
  """Forcibly unleases the build and resets its state.

  Resets status, url and lease_key.

  Returns:
    The reset Build.
  """

  @ndb.transactional
  def txn():
    build = _get_leasable_build(build_id)
    if not user.can_reset_build_async(build).get_result():
      raise user.current_identity_cannot('reset build %s', build.key.id())
    if build.status == model.BuildStatus.COMPLETED:
      raise errors.BuildIsCompletedError('Cannot reset a completed build')
    build.status = model.BuildStatus.SCHEDULED
    build.status_changed_time = utils.utcnow()
    build.clear_lease()
    build.url = None
    build.canary = None
    _fut_results(build.put_async(), events.on_build_resetting_async(build))
    return build

  build = txn()
  events.on_build_reset(build)
  return build


def start(build_id, lease_key, url, canary):
  """Marks build as STARTED. Idempotent.

  Args:
    build_id: id of the started build.
    lease_key: current lease key.
    url (str): a URL to a build-system-specific build, viewable by a human.
    canary (bool): True if canary build infrastructure is used for this build.

  Returns:
    The updated Build.
  """
  assert isinstance(canary, bool), canary
  validate_lease_key(lease_key)
  validate_url(url)

  @ndb.transactional
  def txn():
    build = _get_leasable_build(build_id)

    if build.status == model.BuildStatus.STARTED:
      if build.url == url:
        return False, build
      build.url = url
      build.put()
      return True, build

    if build.status == model.BuildStatus.COMPLETED:
      raise errors.BuildIsCompletedError('Cannot start a completed build')

    assert build.status == model.BuildStatus.SCHEDULED

    _check_lease(build, lease_key)

    build.start_time = utils.utcnow()
    build.status = model.BuildStatus.STARTED
    build.status_changed_time = build.start_time
    build.url = url
    build.canary = canary
    _fut_results(build.put_async(), events.on_build_starting_async(build))
    return True, build

  updated, build = txn()
  if updated:
    events.on_build_started(build)
  return build


def _get_bucket_states(buckets):
  """Returns the list of bucket states for all named buckets.

  Args:
    buckets (list): A list of bucket name strings. The bucket names are assumed
      to have already been validated.

  Returns (dict):
    A map of bucket name to BucketState for that bucket.
  """
  # Get bucket keys and deduplicate.
  default_states = [model.BucketState(id=b) for b in buckets]
  states = ndb.get_multi(state.key for state in default_states)
  for i, state in enumerate(states):
    if not state:
      states[i] = default_states[i]
  return dict(zip(buckets, states))


@ndb.tasklet
def heartbeat_async(build_id, lease_key, lease_expiration_date):
  """Extends build lease.

  Args:
    build_id: id of the build.
    lease_key: current lease key.
    lease_expiration_date (datetime.timedelta): new lease expiration date.

  Returns:
    The updated Build as Future.
  """

  @ndb.transactional_tasklet
  def txn():
    validate_lease_key(lease_key)
    if lease_expiration_date is None:
      raise errors.InvalidInputError('Lease expiration date not specified')
    errors.validate_lease_expiration_date(lease_expiration_date)
    build = yield model.Build.get_by_id_async(build_id)
    if build is None:
      raise errors.BuildNotFoundError()
    if build.status == model.BuildStatus.COMPLETED:
      msg = ''
      if (build.result == model.BuildResult.CANCELED and
          build.cancelation_reason == model.CancelationReason.TIMEOUT):
        msg = (
            'Build was marked as timed out '
            'because it did not complete for %s' % model.BUILD_TIMEOUT
        )
      raise errors.BuildIsCompletedError(msg)
    _check_lease(build, lease_key)
    build.lease_expiration_date = lease_expiration_date
    yield build.put_async()
    raise ndb.Return(build)

  try:
    build = yield txn()
  except Exception as ex:
    events.on_heartbeat_failure(build_id, ex)
    raise
  raise ndb.Return(build)


def heartbeat(build_id, lease_key, lease_expiration_date):
  future = heartbeat_async(build_id, lease_key, lease_expiration_date)
  return future.get_result()


def heartbeat_batch(heartbeats):
  """Extends build leases in a batch.

  Args:
    heartbeats (list of dict): list of builds to update. Each dict is kwargs
    for heartbeat() method.

  Returns:
    List of (build_id, build, exception) tuples.
  """
  build_ids = [h['build_id'] for h in heartbeats]
  logging.info('Batch heartbeat: %s', build_ids)
  futures = [(h, heartbeat_async(**h)) for h in heartbeats]

  def get_result(hb, future):
    build_id = hb['build_id']
    exc = future.get_exception()
    if not exc:
      return build_id, future.get_result(), None
    else:
      return build_id, None, exc

  return [get_result(h, f) for h, f in futures]


def _complete(
    build_id,
    lease_key,
    result,
    result_details,
    failure_reason=None,
    url=None,
    new_tags=None
):
  """Marks a build as completed. Used by succeed and fail methods."""
  validate_lease_key(lease_key)
  validate_url(url)
  buildtags.validate_tags(new_tags, 'append')
  assert result in (model.BuildResult.SUCCESS, model.BuildResult.FAILURE)

  @ndb.transactional
  def txn():
    build = _get_leasable_build(build_id)

    if build.status == model.BuildStatus.COMPLETED:
      if (build.result == result and build.failure_reason == failure_reason and
          build.result_details == result_details and build.url == url):
        return False, build
      raise errors.BuildIsCompletedError(
          'Build %s has already completed' % build_id
      )
    _check_lease(build, lease_key)

    build.status = model.BuildStatus.COMPLETED
    build.status_changed_time = utils.utcnow()
    build.complete_time = utils.utcnow()
    build.result = result
    if url is not None:  # pragma: no branch
      build.url = url
    build.result_details = result_details
    build.failure_reason = failure_reason
    if new_tags:
      build.tags.extend(new_tags)
      build.tags = sorted(set(build.tags))
    build.clear_lease()
    _fut_results(build.put_async(), events.on_build_completing_async(build))
    return True, build

  updated, build = txn()
  if updated:
    events.on_build_completed(build)
  return build


def succeed(build_id, lease_key, result_details=None, url=None, new_tags=None):
  """Marks a build as succeeded. Idempotent.

  Args:
    build_id: id of the build to complete.
    lease_key: current lease key.
    result_details (dict): build result description.
    new_tags (list of str): list of new tags to add to the Build.

  Returns:
    The succeeded Build.
  """
  return _complete(
      build_id,
      lease_key,
      model.BuildResult.SUCCESS,
      result_details,
      url=url,
      new_tags=new_tags
  )


def fail(
    build_id,
    lease_key,
    result_details=None,
    failure_reason=None,
    url=None,
    new_tags=None
):
  """Marks a build as failed. Idempotent.

  Args:
    build_id: id of the build to complete.
    lease_key: current lease key.
    failure_reason (model.FailureReason): why the build failed.
      Defaults to model.FailureReason.BUILD_FAILURE.
    result_details (dict): build result description.
    new_tags (list of str): list of new tags to add to the Build.

  Returns:
    The failed Build.
  """
  failure_reason = failure_reason or model.FailureReason.BUILD_FAILURE
  return _complete(
      build_id,
      lease_key,
      model.BuildResult.FAILURE,
      result_details,
      failure_reason,
      url=url,
      new_tags=new_tags
  )


def cancel(build_id, human_reason=None, result_details=None):
  """Cancels build. Does not require a lease key.

  The current user has to have a permission to cancel a build in the
  bucket.

  Args:
    build_id: id of the build to cancel.
    human_reason (basestring): explanation of cancelation for a human.
    result_details (dict): build result description.

  Returns:
    Canceled Build.
  """

  @ndb.transactional
  def txn():
    build = model.Build.get_by_id(build_id)
    if build is None:
      raise errors.BuildNotFoundError()
    if not user.can_cancel_build_async(build).get_result():
      raise user.current_identity_cannot('cancel build %s', build.key.id())
    if build.status == model.BuildStatus.COMPLETED:
      if build.result == model.BuildResult.CANCELED:
        return False, build
      raise errors.BuildIsCompletedError('Cannot cancel a completed build')
    now = utils.utcnow()
    build.status = model.BuildStatus.COMPLETED
    build.status_changed_time = now
    build.result = model.BuildResult.CANCELED
    build.result_details = result_details
    build.cancelation_reason = model.CancelationReason.CANCELED_EXPLICITLY
    build.cancel_reason_v2 = build_pb2.CancelReason(
        message=human_reason,
        canceled_by=auth.get_current_identity().to_bytes(),
    )
    build.complete_time = now
    build.clear_lease()
    futs = [build.put_async(), events.on_build_completing_async(build)]
    if build.swarming_hostname and build.swarming_task_id is not None:
      futs.append(
          swarming.cancel_task_transactionally_async(
              build.swarming_hostname, build.swarming_task_id
          )
      )
    _fut_results(*futs)
    return True, build

  updated, build = txn()
  if updated:
    events.on_build_completed(build)
  return build


@ndb.tasklet
def _reset_expired_build_async(build_id):

  @ndb.transactional_tasklet
  def txn_async():
    build = yield model.Build.get_by_id_async(build_id)
    if not build or build.lease_expiration_date is None:  # pragma: no cover
      raise ndb.Return(False, build)
    is_expired = build.lease_expiration_date <= utils.utcnow()
    if not is_expired:  # pragma: no cover
      raise ndb.Return(False, build)

    assert build.status != model.BuildStatus.COMPLETED, (
        'Completed build is leased'
    )
    build.clear_lease()
    build.status = model.BuildStatus.SCHEDULED
    build.status_changed_time = utils.utcnow()
    build.url = None
    yield build.put_async(), events.on_build_resetting_async(build)
    raise ndb.Return(True, build)

  updated, build = yield txn_async()
  if updated:  # pragma: no branch
    events.on_expired_build_reset(build)


@ndb.tasklet
def _timeout_async(build_id):

  @ndb.transactional_tasklet
  def txn_async():
    build = yield model.Build.get_by_id_async(build_id)
    if not build or build.status == model.BuildStatus.COMPLETED:
      raise ndb.Return(False, build)  # pragma: no cover

    now = utils.utcnow()
    build.clear_lease()
    build.status = model.BuildStatus.COMPLETED
    build.complete_time = now
    build.status_changed_time = now
    build.result = model.BuildResult.CANCELED
    build.cancelation_reason = model.CancelationReason.TIMEOUT
    yield build.put_async(), events.on_build_completing_async(build)
    raise ndb.Return(True, build)

  # This is the only yield in this function, but it is not performance-critical.
  updated, build = yield txn_async()
  if updated:  # pragma: no branch
    events.on_build_completed(build)


def check_expired_builds():
  """For all building expired builds, resets their lease_key and state."""
  futures = []

  q = model.Build.query(
      model.Build.is_leased == True,
      model.Build.lease_expiration_date <= datetime.datetime.utcnow(),
  )
  for key in q.iter(keys_only=True):
    futures.append(_reset_expired_build_async(key.id()))

  too_long_ago = utils.utcnow() - model.BUILD_TIMEOUT
  q = model.Build.query(
      model.Build.create_time < too_long_ago,
      # Cannot use >1 inequality fitlers per query.
      model.Build.status.IN([
          model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED
      ]),
  )
  for key in q.iter(keys_only=True):
    futures.append(_timeout_async(key.id()))

  _fut_results(*futures)


def delete_many_builds(bucket, status, tags=None, created_by=None):
  if status not in (model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED):
    raise errors.InvalidInputError(
        'status can be STARTED or SCHEDULED, not %s' % status
    )
  if not user.can_delete_scheduled_builds_async(bucket).get_result():
    raise user.current_identity_cannot('delete scheduled builds of %s', bucket)
  # Validate created_by prior scheduled a push task.
  created_by = user.parse_identity(created_by)
  deferred.defer(
      _task_delete_many_builds,
      bucket,
      status,
      tags=tags,
      created_by=created_by,
      # Schedule it on the backend module of the same version.
      # This assumes that both frontend and backend are uploaded together.
      _target='%s.backend' % modules.get_current_version_name(),
      # Retry immediatelly.
      _retry_options=taskqueue.TaskRetryOptions(
          min_backoff_seconds=0,
          max_backoff_seconds=1,
      ),
  )


def _task_delete_many_builds(bucket, status, tags=None, created_by=None):

  @ndb.transactional_tasklet
  def txn(key):
    build = yield key.get_async()
    if not build or build.status != status:  # pragma: no cover
      raise ndb.Return(False)
    futs = [key.delete_async()]
    if build.swarming_hostname and build.swarming_task_id:
      futs.append(
          swarming.cancel_task_transactionally_async(
              build.swarming_hostname, build.swarming_task_id
          )
      )
    yield futs
    raise ndb.Return(True)

  @ndb.tasklet
  def del_if_unchanged(key):
    if (yield txn(key)):  # pragma: no branch
      logging.debug('Deleted %s', key.id())

  assert status in (model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED)
  tags = tags or []
  created_by = user.parse_identity(created_by)
  q = model.Build.query(
      model.Build.bucket == bucket, model.Build.status == status
  )
  for t in tags:
    q = q.filter(model.Build.tags == t)
  if created_by:
    q = q.filter(model.Build.created_by == created_by)
  q.map(del_if_unchanged, keys_only=True)


def pause(bucket, is_paused):
  if not user.can_pause_buckets_async(bucket).get_result():
    raise user.current_identity_cannot('pause bucket of %s', bucket)

  validate_bucket_name(bucket)
  _, cfg = config.get_bucket(bucket)
  if not cfg:
    raise errors.InvalidInputError('Invalid bucket: %s' % (bucket,))
  if config.is_swarming_config(cfg):
    raise errors.InvalidInputError('Cannot pause a Swarming bucket')

  @ndb.transactional
  def try_set_pause():
    state = (
        model.BucketState.get_by_id(id=bucket) or model.BucketState(id=bucket)
    )
    if state.is_paused != is_paused:
      state.is_paused = is_paused
      state.put()

  try_set_pause()


def _fut_results(*futures):
  return [f.get_result() for f in futures]
