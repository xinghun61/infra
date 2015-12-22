# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import urlparse

from google.appengine.api import taskqueue
from google.appengine.api import modules
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext import ndb

from components import auth
from components import utils

import acl
import errors
import metrics
import model
import notifications
import swarming

MAX_RETURN_BUILDS = 100
MAX_LEASE_DURATION = datetime.timedelta(hours=2)
DEFAULT_LEASE_DURATION = datetime.timedelta(minutes=1)

validate_bucket_name = errors.validate_bucket_name


def validate_lease_key(lease_key):
  if lease_key is None:
    raise errors.InvalidInputError('Lease key is not provided')


def validate_lease_expiration_date(expiration_date):
  """Raises errors.InvalidInputError if |expiration_date| is invalid."""
  if expiration_date is None:
    return
  if not isinstance(expiration_date, datetime.datetime):
    raise errors.InvalidInputError(
      'Lease expiration date must be datetime.datetime')
  duration = expiration_date - utils.utcnow()
  if duration <= datetime.timedelta(0):
    raise errors.InvalidInputError(
      'Lease expiration date cannot be in the past')
  if duration > MAX_LEASE_DURATION:
    raise errors.InvalidInputError(
      'Lease duration cannot exceed %s' % MAX_LEASE_DURATION)


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
      'Unexpected url scheme: "%s"' % parsed.scheme)


def fix_max_builds(max_builds):
  max_builds = max_builds or 10
  if not isinstance(max_builds, int):
    raise errors.InvalidInputError('max_builds must be an integer')
  if max_builds < 0:
    raise errors.InvalidInputError('max_builds must be positive')
  return min(MAX_RETURN_BUILDS, max_builds)


def validate_tags(tags):
  if tags is None:
    return
  if not isinstance(tags, list):
    raise errors.InvalidInputError('tags must be a list')
  for t in tags:
    if not isinstance(t, basestring):
      raise errors.InvalidInputError('Invalid tag "%s": must be a string')
    if ':' not in t:
      raise errors.InvalidInputError('Invalid tag "%s": does not contain ":"')


def current_identity_cannot(action_format, *args):
  action = action_format % args
  msg = 'User %s cannot %s' % (auth.get_current_identity().to_bytes(), action)
  logging.warning(msg)
  raise auth.AuthorizationError(msg)


@ndb.tasklet
def add_async(
    bucket, tags=None, parameters=None, lease_expiration_date=None,
    client_operation_id=None, pubsub_callback=None):
  """Adds the build entity to the build bucket.

  Requires the current user to have permissions to add builds to the
  |bucket|.

  Args:
    bucket (str): destination bucket. Required.
    tags (model.Tags): build tags.
    parameters (dict): arbitrary build parameters. Cannot be changed after
      build creation.
    lease_expiration_date (datetime.datetime): if not None, the build is
      created as leased and its lease_key is not None.
    pubsub_callback (model.PubsubCallback): callback parameters.
    client_operation_id (str): client-supplied operation id. If an
      a build with the same client operation id was added during last minute,
      it will be returned instead.

  Returns:
    A new Build.
  """
  if client_operation_id is not None:
    if not isinstance(client_operation_id, basestring):  # pragma: no cover
      raise errors.InvalidInputError('client_operation_id must be string')
    if '/' in client_operation_id:  # pragma: no cover
      raise errors.InvalidInputError('client_operation_id must not contain /')
  validate_bucket_name(bucket)
  if parameters is not None and not isinstance(parameters, dict):
    raise errors.InvalidInputError('parameters must be a dict or None')
  validate_lease_expiration_date(lease_expiration_date)
  validate_tags(tags)
  tags = tags or []

  ctx = ndb.get_context()
  identity = auth.get_current_identity()
  if not (yield acl.can_add_build_async(bucket)):  # pragma: no branch
    raise current_identity_cannot('add builds to bucket %s', bucket)

  if client_operation_id is not None:
    client_operation_cache_key = (
      'client_op/%s/%s/add_build' % (
        identity.to_bytes(), client_operation_id))
    build_id = yield ctx.memcache_get(client_operation_cache_key)
    if build_id:
      build = yield model.Build.get_by_id_async(build_id)
      if build:  # pragma: no branch
        raise ndb.Return(build)

  build = model.Build(
    id=model.new_build_id(),
    bucket=bucket,
    tags=tags,
    parameters=parameters,
    status=model.BuildStatus.SCHEDULED,
    created_by=identity,
    never_leased=lease_expiration_date is None,
    pubsub_callback=pubsub_callback,
  )
  if lease_expiration_date is not None:
    build.lease_expiration_date = lease_expiration_date
    build.leasee = auth.get_current_identity()
    build.regenerate_lease_key()

  for_swarming = yield swarming.is_for_swarming_async(build)
  if for_swarming:  # pragma: no cover
    yield swarming.create_task_async(build)

  try:
    yield build.put_async()
  except:  # pragma: no cover
    # Best effort.
    if for_swarming:
      yield swarming.cancel_task_async(build)
    raise
  logging.info(
    'Build %s was created by %s', build.key.id(), identity.to_bytes())
  metrics.increment(metrics.CREATE_COUNT, build)

  if client_operation_id is not None:
    yield ctx.memcache_set(client_operation_cache_key, build.key.id(), 60)
  raise ndb.Return(build)


def add(*args, **kwargs):
  """Sync version of add_async."""
  return add_async(*args, **kwargs).get_result()


def get(build_id):
  """Gets a build by |build_id|.

  Requires the current user to have permissions to view the build.
  """
  build = model.Build.get_by_id(build_id)
  if not build:
    return None
  if not acl.can_view_build(build):
    raise current_identity_cannot('view build %s', build.key.id())
  return build


def _fetch_page(query, page_size, start_cursor, predicate=None):
  assert query
  assert isinstance(page_size, int)
  assert start_cursor is None or isinstance(start_cursor, basestring)

  curs = None
  if start_cursor:
    try:
      curs = ndb.Cursor(urlsafe=start_cursor)
    except db.BadValueError as ex:
      msg = 'Bad cursor "%s": %s' % (start_cursor, ex)
      logging.warning(msg)
      raise errors.InvalidInputError(msg)

  query_iter = query.iter(
    start_cursor=curs, produce_cursors=True, batch_size=page_size)
  entities = []
  for entity in query_iter:
    if predicate is None or predicate(entity):  # pragma: no branch
      entities.append(entity)
      if len(entities) >= page_size:
        break

  next_cursor_str = None
  if query_iter.has_next():
    next_cursor_str = query_iter.cursor_after().urlsafe()
  return entities, next_cursor_str


def _check_search_acls(buckets):
  if not buckets:
    raise errors.InvalidInputError('No buckets specified')
  for bucket in buckets:
    validate_bucket_name(bucket)

  for bucket in buckets:
    if not acl.can_search_builds(bucket):
      raise current_identity_cannot('search builds in bucket %s', bucket)


def search(
    buckets=None, tags=None,
    status=None, result=None, failure_reason=None, cancelation_reason=None,
    created_by=None, max_builds=None, start_cursor=None):
  """Searches for builds.

  Args:
    buckets (list of str): a list of buckets to search in.
      A build must be in one of the buckets.
    tags (list of str): a list of tags that a build must have.
      All of the |tags| must be present in a build.
    status (model.BuildStatus): build status.
    result (model.BuildResult): build result.
    failure_reason (model.FailureReason): failure reason.
    cancelation_reason (model.CancelationReason): build cancelation reason.
    created_by (str): identity who created a build.
    max_builds (int): maximum number of builds to return.
    start_cursor (string): a value of "next" cursor returned by previous
      search_by_tags call. If not None, return next builds in the query.

  Returns:
    A tuple:
      builds (list of Build): query result.
      next_cursor (string): cursor for the next page.
        None if there are no more builds.
  """
  if buckets is not None and not isinstance(buckets, list):
    raise errors.InvalidInputError('Buckets must be a list or None')
  validate_tags(tags)
  tags = tags or []
  max_builds = fix_max_builds(max_builds)
  created_by = parse_identity(created_by)

  if buckets:
    _check_search_acls(buckets)
  else:
    buckets = acl.get_available_buckets()
    if buckets is not None and len(buckets) == 0:
      return [], None
  if buckets:
    buckets = set(buckets)
  assert buckets is None or buckets

  check_buckets_locally = False
  q = model.Build.query()
  for t in tags:
    if t.startswith('buildset:'):
      check_buckets_locally = True
    q = q.filter(model.Build.tags == t)
  filter_if = lambda p, v: q if v is None else q.filter(p == v)
  q = filter_if(model.Build.status, status)
  q = filter_if(model.Build.result, result)
  q = filter_if(model.Build.failure_reason, failure_reason)
  q = filter_if(model.Build.cancelation_reason, cancelation_reason)
  q = filter_if(model.Build.created_by, created_by)
  # buckets is None if the current identity has access to ALL buckets.
  if buckets and not check_buckets_locally:
    q = q.filter(model.Build.bucket.IN(buckets))
  q = q.order(model.Build.key)

  local_predicate = None

  def local_status_and_bucket_check(build):
    if status is not None and build.status != status:  # pragma: no coverage
      return False
    if buckets and build.bucket not in buckets:
      return False
    return True

  if status is not None or (buckets and check_buckets_locally):
    local_predicate = local_status_and_bucket_check

  return _fetch_page(
    q, max_builds, start_cursor, predicate=local_predicate)


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
  _check_search_acls(buckets)
  max_builds = fix_max_builds(max_builds)

  q = model.Build.query(
    model.Build.status == model.BuildStatus.SCHEDULED,
    model.Build.is_leased == False,
    model.Build.bucket.IN(buckets),
  )
  q = q.order(-model.Build.key)  # oldest first.

  # Check once again locally because an ndb query may return an entity not
  # satisfying the query.
  def local_predicate(b):
    return (b.status == model.BuildStatus.SCHEDULED and
            not b.is_leased and
            b.bucket in buckets)

  return _fetch_page(
    q, max_builds, start_cursor, predicate=local_predicate)


def _get_leasable_build(build_id):
  build = model.Build.get_by_id(build_id)
  if build is None:
    raise errors.BuildNotFoundError()
  if not acl.can_lease_build(build):
    raise current_identity_cannot('lease build %s', build.key.id())
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
  validate_lease_expiration_date(lease_expiration_date)
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

  leased, build = try_lease()
  if leased:
    logging.info(
      'Build %s was leased by %s', build.key.id(), build.leasee.to_bytes())
    metrics.increment(metrics.LEASE_COUNT, build)
  return leased, build


def _check_lease(build, lease_key):
  if lease_key != build.lease_key:
    raise errors.LeaseExpiredError(
      'lease_key for build %s is incorrect. Your lease might be expired.' %
      build.key.id())


@ndb.transactional
def reset(build_id):
  """Forcibly unleases the build and resets its state. Idempotent.

  Resets status, url and lease_key.

  Returns:
    The reset Build.
  """
  build = _get_leasable_build(build_id)
  if not acl.can_reset_build(build):
    raise current_identity_cannot('reset build %s', build.key.id())
  if build.status == model.BuildStatus.COMPLETED:
    raise errors.BuildIsCompletedError('Cannot reset a completed build')
  build.status = model.BuildStatus.SCHEDULED
  build.status_changed_time = utils.utcnow()
  build.clear_lease()
  build.url = None
  build.put()
  notifications.enqueue_callback_task_if_needed(build)
  logging.info(
    'Build %s was reset by %s',
    build.key.id(), auth.get_current_identity().to_bytes())
  return build


def start(build_id, lease_key, url=None):
  """Marks build as STARTED. Idempotent.

  Args:
    build_id: id of the started build.
    lease_key: current lease key.
    url (str): a URL to a build-system-specific build, viewable by a human.

  Returns:
    The updated Build.
  """
  validate_lease_key(lease_key)
  validate_url(url)

  @ndb.transactional
  def txn():
    build = _get_leasable_build(build_id)

    if build.status == model.BuildStatus.STARTED:
      if build.url != url:
        build.url = url
        build.put()
      return build
    elif build.status == model.BuildStatus.COMPLETED:
      raise errors.BuildIsCompletedError('Cannot start a completed build')
    assert build.status == model.BuildStatus.SCHEDULED
    _check_lease(build, lease_key)

    build.status = model.BuildStatus.STARTED
    build.status_changed_time = utils.utcnow()
    build.url = url
    build.put()
    notifications.enqueue_callback_task_if_needed(build)
    return build

  build = txn()
  logging.info('Build %s was started. URL: %s', build.key.id(), url)
  metrics.increment(metrics.START_COUNT, build)
  return build


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
    validate_lease_expiration_date(lease_expiration_date)
    build = yield model.Build.get_by_id_async(build_id)
    if build is None:
      raise errors.BuildNotFoundError()
    if build.status == model.BuildStatus.COMPLETED:
      raise errors.BuildIsCompletedError()
    _check_lease(build, lease_key)
    build.lease_expiration_date = lease_expiration_date
    yield build.put_async()
    raise ndb.Return(build)

  build = None
  try:
    build = yield txn()
  except Exception as ex:
    logging.warning('Heartbeat for build %s failed: %s', build_id, ex)
    metrics.increment(metrics.HEARTBEAT_COUNT, build, status='FAILURE')
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
    build_id, lease_key, result, result_details, failure_reason=None,
    url=None):
  """Marks a build as completed. Used by succeed and fail methods."""
  validate_lease_key(lease_key)
  validate_url(url)
  assert result in (model.BuildResult.SUCCESS, model.BuildResult.FAILURE)

  @ndb.transactional
  def txn():
    build = _get_leasable_build(build_id)

    if build.status == model.BuildStatus.COMPLETED:
      if (build.result == result and
          build.failure_reason == failure_reason and
          build.result_details == result_details and
          build.url == url):
        return build
      raise errors.BuildIsCompletedError(
        'Build %s has already completed' % build_id)
    _check_lease(build, lease_key)

    build.status = model.BuildStatus.COMPLETED
    build.status_changed_time = utils.utcnow()
    build.complete_time = utils.utcnow()
    build.result = result
    if url is not None:  # pragma: no branch
      build.url = url
    build.result_details = result_details
    build.failure_reason = failure_reason
    build.clear_lease()
    build.put()
    notifications.enqueue_callback_task_if_needed(build)
    return build

  build = txn()
  logging.info(
    'Build %s was completed. Status: %s. Result: %s',
    build.key.id(), build.status, build.result)
  metrics.increment_complete_count(build)
  return build


def succeed(build_id, lease_key, result_details=None, url=None):
  """Marks a build as succeeded. Idempotent.

  Args:
    build_id: id of the build to complete.
    lease_key: current lease key.
    result_details (dict): build result description.

  Returns:
    The succeeded Build.
  """
  return _complete(
    build_id, lease_key, model.BuildResult.SUCCESS, result_details, url=url)


def fail(
    build_id, lease_key, result_details=None, failure_reason=None,
    url=None):
  """Marks a build as failed. Idempotent.

  Args:
    build_id: id of the build to complete.
    lease_key: current lease key.
    failure_reason (model.FailureReason): why the build failed.
      Defaults to model.FailureReason.BUILD_FAILURE.
    result_details (dict): build result description.

  Returns:
    The failed Build.
  """
  failure_reason = failure_reason or model.FailureReason.BUILD_FAILURE
  return _complete(
    build_id, lease_key, model.BuildResult.FAILURE, result_details,
    failure_reason, url=url)


def cancel(build_id):
  """Cancels build. Does not require a lease key.

  The current user has to have a permission to cancel a build in the
  bucket.

  Returns:
    Canceled Build.
  """
  @ndb.transactional
  def txn():
    build = model.Build.get_by_id(build_id)
    if build is None:
      raise errors.BuildNotFoundError()
    if not acl.can_cancel_build(build):
      raise current_identity_cannot('cancel build %s', build.key.id())
    if build.status == model.BuildStatus.COMPLETED:
      if build.result == model.BuildResult.CANCELED:
        return build
      raise errors.BuildIsCompletedError('Cannot cancel a completed build')
    now = utils.utcnow()
    build.status = model.BuildStatus.COMPLETED
    build.status_changed_time = now
    build.result = model.BuildResult.CANCELED
    build.cancelation_reason = model.CancelationReason.CANCELED_EXPLICITLY
    build.complete_time = now
    build.clear_lease()
    build.put()
    notifications.enqueue_callback_task_if_needed(build)
    return build

  build = txn()
  logging.info(
    'Build %s was cancelled by %s', build.key.id(),
    auth.get_current_identity().to_bytes())
  metrics.increment_complete_count(build)
  return build


@ndb.tasklet
def _reset_expired_build_async(build_id):
  @ndb.transactional_tasklet
  def txn():
    build = yield model.Build.get_by_id_async(build_id)
    if not build or build.lease_expiration_date is None:  # pragma: no cover
      return
    is_expired = build.lease_expiration_date <= utils.utcnow()
    if not is_expired:  # pragma: no cover
      return

    assert build.status != model.BuildStatus.COMPLETED, (
      'Completed build is leased')
    build.clear_lease()
    build.status = model.BuildStatus.SCHEDULED
    build.status_changed_time = utils.utcnow()
    build.url = None
    yield build.put_async()
    raise ndb.Return(build)

  build = yield txn()
  logging.info('Expired build %s was reset', build_id)
  metrics.increment(metrics.LEASE_EXPIRATION_COUNT, build)


@ndb.transactional_tasklet
def _timeout_async(build_id):
  build = yield model.Build.get_by_id_async(build_id)
  if not build or build.status == model.BuildStatus.COMPLETED:
    return  # pragma: no cover

  build.clear_lease()
  build.status = model.BuildStatus.COMPLETED
  build.status_changed_time = utils.utcnow()
  build.result = model.BuildResult.CANCELED
  build.cancelation_reason = model.CancelationReason.TIMEOUT
  yield build.put_async()
  logging.info('Build %s: timeout', build_id)
  notifications.enqueue_callback_task_if_needed(build)
  metrics.increment_complete_count(build)


def reset_expired_builds():
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
    model.Build.status.IN(
      [model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED]),
  )
  for key in q.iter(keys_only=True):
    futures.append(_timeout_async(key.id()))

  ndb.Future.wait_all(futures)


def delete_many_builds(bucket, status, tags=None, created_by=None):
  if status not in (model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED):
    raise errors.InvalidInputError(
      'status can be STARTED or SCHEDULED, not %s' % status)
  if not acl.can_delete_scheduled_builds(bucket):
    raise current_identity_cannot('delete scheduled builds of %s', bucket)
  # Validate created_by prior scheduled a push task.
  created_by = parse_identity(created_by)
  deferred.defer(
    _task_delete_many_builds,
    bucket,
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
  def del_if_unchanged(key):
    build = yield key.get_async()
    if build and build.status == status:  # pragma: no branch
      yield key.delete_async()
      logging.debug('Deleted %s', key.id())

  assert status in (model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED)
  tags = tags or []
  created_by = parse_identity(created_by)
  q = model.Build.query(
    model.Build.bucket == bucket,
    model.Build.status == status)
  for t in tags:
    q = q.filter(model.Build.tags == t)
  if created_by:
    q = q.filter(model.Build.created_by == created_by)
  q.map(del_if_unchanged, keys_only=True)


def parse_identity(identity):
  if isinstance(identity, basestring):
    if not identity:  # pragma: no cover
      return None
    if ':' not in identity:  # pragma: no branch
      identity = 'user:%s' % identity
    try:
      identity = auth.Identity.from_bytes(identity)
    except ValueError as ex:
      raise errors.InvalidInputError('Invalid identity identity: %s' % ex)
  return identity
