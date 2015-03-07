# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import itertools
import json
import logging
import urlparse

from components import auth
from components import utils
from google.appengine.api import taskqueue
from google.appengine.ext import db
from google.appengine.ext import ndb

import acl
import errors
import model


MAX_RETURN_BUILDS = 100
MAX_LEASE_DURATION = datetime.timedelta(minutes=10)
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


class BuildBucketService(object):
  def add(
      self, bucket, tags=None, parameters=None, lease_expiration_date=None):
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

    Returns:
      A new Build.
    """
    validate_bucket_name(bucket)
    assert parameters is None or isinstance(parameters, dict)
    validate_lease_expiration_date(lease_expiration_date)
    validate_tags(tags)
    tags = tags or []

    identity = auth.get_current_identity()
    if not acl.can_add_build(bucket, identity):
      raise current_identity_cannot('add builds to bucket %s', bucket)

    build = model.Build(
        id=model.new_build_id(),
        bucket=bucket,
        tags=tags,
        parameters=parameters,
        status=model.BuildStatus.SCHEDULED,
        created_by=identity,
    )
    if lease_expiration_date is not None:
      build.lease_expiration_date = lease_expiration_date
      build.leasee = auth.get_current_identity()
      build.regenerate_lease_key()
    build.put()
    logging.info(
        'Build %s was created by %s', build.key.id(), identity.to_bytes())
    return build

  def get(self, build_id):
    """Gets a build by |build_id|.

    Requires the current user to have permissions to view the build.
    """
    build = model.Build.get_by_id(build_id)
    if not build:
      return None
    identity = auth.get_current_identity()
    if not acl.can_view_build(build, identity):
      raise current_identity_cannot('view build %s', build.key.id())
    return build

  def _fetch_page(self, query, page_size, start_cursor, predicate=None):
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

    query_iter = query.iter(start_cursor=curs, produce_cursors=True)
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

  def _check_search_acls(self, buckets):
    if not buckets:
      raise errors.InvalidInputError('No buckets specified')
    for bucket in buckets:
      validate_bucket_name(bucket)

    identity = auth.get_current_identity()
    for bucket in buckets:
      if not acl.can_search_builds(bucket, identity):
        raise current_identity_cannot('search builds in bucket %s', bucket)

  def search(self, buckets=None, tags=None, max_builds=None, start_cursor=None):
    """Searches for builds.

    Args:
      buckets (list of str): a list of buckets to search in.
        A build must be in one of the buckets.
      tags (list of str): a list of tags that a build must have.
        All of the |tags| must be present in a build.
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

    if buckets:
      self._check_search_acls(buckets)
    else:
      buckets = acl.get_available_buckets()
      if buckets is not None and len(buckets) == 0:
        return [], None

    q = model.Build.query()
    # buckets is None if the current identity has access to ALL buckets.
    if buckets is not None:
      q = q.filter(model.Build.bucket.IN(buckets))
    for t in tags:
      q = q.filter(model.Build.tags == t)
    q = q.order(model.Build.key)
    return self._fetch_page(q, max_builds, start_cursor)

  def peek(self, buckets, max_builds=None, start_cursor=None):
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
    self._check_search_acls(buckets)
    max_builds = fix_max_builds(max_builds)

    q = model.Build.query(
        model.Build.status == model.BuildStatus.SCHEDULED,
        model.Build.is_leased == False,
        model.Build.bucket.IN(buckets),
    )
    q = q.order(model.Build.create_time) # oldest first.

    # Check once again locally because an ndb query may return an entity not
    # satisfying the query.
    def local_predicate(b):
      return (b.status == model.BuildStatus.SCHEDULED and
              not b.is_leased and
              b.bucket in buckets)

    return self._fetch_page(
        q, max_builds, start_cursor, predicate=local_predicate)

  def _get_leasable_build(self, build_id):
    build = model.Build.get_by_id(build_id)
    if build is None:
      raise errors.BuildNotFoundError()
    identity = auth.get_current_identity()
    if not acl.can_lease_build(build, identity):
      raise current_identity_cannot('lease build %s', build.key.id())
    return build

  def lease(self, build_id, lease_expiration_date=None):
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

    identity = auth.get_current_identity()

    @ndb.transactional
    def try_lease():
      build = self._get_leasable_build(build_id)

      if build.status != model.BuildStatus.SCHEDULED or build.is_leased:
        return False, build

      build.lease_expiration_date = lease_expiration_date
      build.regenerate_lease_key()
      build.leasee = identity
      build.put()
      logging.info(
          'Build %s was leased by %s', build.key.id(), build.leasee.to_bytes())
      return True, build

    return try_lease()

  def _check_lease(self, build, lease_key):
    if lease_key != build.lease_key:
      raise errors.LeaseExpiredError(
          'lease_key for build %s is incorrect. Your lease might be expired.' %
          build.key.id())

  def _clear_lease(self, build):
    """Clears build's lease attributes."""
    build.lease_key = None
    build.lease_expiration_date = None
    build.leasee = None

  @ndb.transactional
  def reset(self, build_id):
    """Forcibly unleases the build and resets its state. Idempotent.

    Resets status, url and lease_key.

    Returns:
      The reset Build.
    """
    build = self._get_leasable_build(build_id)
    if not acl.can_reset_build(build):
      raise current_identity_cannot('reset build %s', build.key.id())
    if build.status == model.BuildStatus.COMPLETED:
      raise errors.BuildIsCompletedError('Cannot reset a completed build')
    build.status = model.BuildStatus.SCHEDULED
    build.status_changed_time = utils.utcnow()
    self._clear_lease(build)
    build.url = None
    build.put()
    logging.info(
        'Build %s was reset by %s',
        build.key.id(), auth.get_current_identity().to_bytes())
    return build

  @staticmethod
  def _enqueue_callback_task_if_needed(build):
    assert ndb.in_transaction()
    assert build
    if not build.callback:
      return
    task = taskqueue.Task(
        url=build.callback.url,
        headers=build.callback.headers,
        payload=json.dumps({
            'build_id': build.key.id(),
        }),
    )
    add_kwargs = {}
    if build.callback.queue_name:  # pragma: no branch
      add_kwargs['queue_name'] = build.callback.queue_name
    task.add(transactional=True, **add_kwargs)

  @ndb.transactional
  def start(self, build_id, lease_key, url=None):
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
    build = self._get_leasable_build(build_id)

    if build.status == model.BuildStatus.STARTED:
      if build.url != url:
        build.url = url
        build.put()
      return build
    elif build.status == model.BuildStatus.COMPLETED:
      raise errors.BuildIsCompletedError('Cannot start a completed build')
    assert build.status == model.BuildStatus.SCHEDULED
    self._check_lease(build, lease_key)

    build.status = model.BuildStatus.STARTED
    build.status_changed_time = utils.utcnow()
    build.url = url
    build.put()
    logging.info('Build %s was started. URL: %s', build.key.id(), url)
    self._enqueue_callback_task_if_needed(build)
    return build

  @ndb.transactional_tasklet
  def heartbeat_async(self, build_id, lease_key, lease_expiration_date):
    """Extends build lease.

    Args:
      build_id: id of the build.
      lease_key: current lease key.
      lease_expiration_date (datetime.timedelta): new lease expiration date.

    Returns:
      The updated Build as Future.
    """
    validate_lease_key(lease_key)
    if lease_expiration_date is None:
      raise errors.InvalidInputError('Lease expiration date not specified')
    validate_lease_expiration_date(lease_expiration_date)
    build = yield model.Build.get_by_id_async(build_id)
    if build is None:
      raise errors.BuildNotFoundError()
    self._check_lease(build, lease_key)
    build.lease_expiration_date = lease_expiration_date
    yield build.put_async()
    raise ndb.Return(build)

  def heartbeat(self, build_id, lease_key, lease_expiration_date):
    future = self.heartbeat_async(build_id, lease_key, lease_expiration_date)
    return future.get_result()

  def heartbeat_batch(self, heartbeats):
    """Extends build leases in a batch.

    Args:
      heartbeats (list of dict): list of builds to update. Each dict is kwargs
      for heartbeat() method.

    Returns:
      List of (build_id, build, exception) tuples.
    """
    futures = [(h, self.heartbeat_async(**h)) for h in heartbeats]

    def get_result(heartbeat, future):
      build_id = heartbeat['build_id']
      exc = future.get_exception()
      if not exc:
        return build_id, future.get_result(), None
      else:
        return build_id, None, exc

    return [get_result(h, f) for h, f in futures]

  @ndb.transactional
  def _complete(
        self, build_id, lease_key, result, result_details, failure_reason=None,
        url=None):
    """Marks a build as completed. Used by succeed and fail methods."""
    validate_lease_key(lease_key)
    validate_url(url)
    assert result in (model.BuildResult.SUCCESS, model.BuildResult.FAILURE)
    build = self._get_leasable_build(build_id)

    if build.status == model.BuildStatus.COMPLETED:
      if (build.result == result and
          build.failure_reason == failure_reason and
          build.result_details == result_details and
          build.url == url):
        return build
      raise errors.InvalidBuildStateError(
          'Build %s has already completed' % build_id)
    self._check_lease(build, lease_key)

    build.status = model.BuildStatus.COMPLETED
    build.status_changed_time = utils.utcnow()
    build.complete_time = utils.utcnow()
    build.result = result
    if url is not None:  # pragma: no branch
      build.url = url
    build.result_details = result_details
    build.failure_reason = failure_reason
    self._clear_lease(build)
    build.put()
    logging.info(
        'Build %s was completed. Status: %s. Result: %s',
        build.key.id(), build.status, build.result)
    self._enqueue_callback_task_if_needed(build)
    return build

  def succeed(self, build_id, lease_key, result_details=None, url=None):
    """Marks a build as succeeded. Idempotent.

    Args:
      build_id: id of the build to complete.
      lease_key: current lease key.
      result_details (dict): build result description.

    Returns:
      The succeeded Build.
    """
    return self._complete(
        build_id, lease_key, model.BuildResult.SUCCESS, result_details, url=url)

  def fail(
        self, build_id, lease_key, result_details=None, failure_reason=None,
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
    return self._complete(
        build_id, lease_key, model.BuildResult.FAILURE, result_details,
        failure_reason, url=url)

  @ndb.transactional
  def cancel(self, build_id):
    """Cancels build. Does not require a lease key.

    The current user has to have a permission to cancel a build in the
    bucket.

    Returns:
      Canceled Build.
    """
    build = model.Build.get_by_id(build_id)
    if build is None:
      raise errors.BuildNotFoundError()
    identity = auth.get_current_identity()
    if not acl.can_cancel_build(build, identity):
      raise current_identity_cannot('cancel build %s', build.key.id())
    if build.status == model.BuildStatus.COMPLETED:
      if build.result == model.BuildResult.CANCELED:
        return build
      raise errors.InvalidBuildStateError('Cannot cancel a completed build')
    build.status = model.BuildStatus.COMPLETED
    build.status_changed_time = utils.utcnow()
    build.result = model.BuildResult.CANCELED
    build.cancelation_reason = model.CancelationReason.CANCELED_EXPLICITLY
    self._clear_lease(build)
    build.put()
    logging.info(
        'Build %s was cancelled by %s', build.key.id(), identity.to_bytes())
    return build

  @ndb.transactional
  def _reset_expired_build(self, build_key):
    build = build_key.get()
    if not build or build.lease_expiration_date is None:  # pragma: no cover
      return False
    is_expired = build.lease_expiration_date <= utils.utcnow()
    if not is_expired:  # pragma: no cover
      return False

    assert build.status != model.BuildStatus.COMPLETED, (
        'Completed build is leased')
    self._clear_lease(build)
    build.status = model.BuildStatus.SCHEDULED
    build.status_changed_time = utils.utcnow()
    build.url = None
    build.put()
    return True

  def reset_expired_builds(self):
    """For all building expired builds, resets their lease_key and state."""
    q = model.Build.query(
        model.Build.is_leased == True,
        model.Build.lease_expiration_date <= datetime.datetime.utcnow(),
    )
    for key in q.iter(keys_only=True):
      if self._reset_expired_build(key):  # pragma: no branch
        logging.info('Expired build %s was reset' % key.id())
