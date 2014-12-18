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
from google.appengine.ext import ndb

from . import model
import acl


MAX_PEEK_BUILDS = 100
MAX_LEASE_DURATION = datetime.timedelta(minutes=10)
DEFAULT_LEASE_DURATION = datetime.timedelta(minutes=1)


class BuildNotFoundError(Exception):
  pass


class InvalidBuildStateError(Exception):
  """Build status is final and cannot be changed."""


class InvalidInputError(Exception):
  """Raised when service method argument value is invalid."""


def validate_lease_key(lease_key):
  if lease_key is None:
    raise InvalidInputError('Lease key is not provided')


def validate_lease_expiration_date(expiration_date):
  """Raises InvalidInputError if |expiration_date| is invalid."""
  if expiration_date is None:
    return
  if not isinstance(expiration_date, datetime.datetime):
    raise InvalidInputError('Lease expiration date must be datetime.datetime')
  duration = expiration_date - utils.utcnow()
  if duration <= datetime.timedelta(0):
    raise InvalidInputError('Lease expiration date cannot be in the past')
  if duration > MAX_LEASE_DURATION:
    raise InvalidInputError(
        'Lease duration cannot exceed %s' % MAX_LEASE_DURATION)


def validate_url(url):
  if url is None:
    return
  if not isinstance(url, basestring):
    raise InvalidInputError('url must be string')
  parsed = urlparse.urlparse(url)
  if not parsed.netloc:
    raise InvalidInputError('url must be absolute')
  if parsed.scheme.lower() not in ('http', 'https'):
    raise InvalidInputError('Unexpected url scheme: "%s"' % parsed.scheme)


class BuildBucketService(object):
  def add(self, namespace, parameters=None, lease_expiration_date=None):
    """Adds the build entity to the build bucket.

    Requires the current user to have permissions to add builds to the
    |namespace|.

    Args:
      namespace (str): build namespace. Required.
      parameters (dict): arbitrary build parameters. Cannot be changed after
        build creation.
      lease_expiration_date (datetime.datetime): if not None, the build is
        created as leased and its lease_key is not None.

    Returns:
      A new Build.
    """
    assert namespace, 'Namespace not specified'
    assert isinstance(namespace, basestring), 'Namespace must be a string'
    assert parameters is None or isinstance(parameters, dict)
    validate_lease_expiration_date(lease_expiration_date)

    acl_user = acl.current_user()
    if not acl_user.can_add_build_to_namespace(namespace):
      raise auth.AuthorizationError(
          'namespace %s is not allowed for %s' % (namespace, acl_user))

    build = model.Build(
        namespace=namespace,
        parameters=parameters,
        status=model.BuildStatus.SCHEDULED,
    )
    if lease_expiration_date is not None:
      build.lease_expiration_date = lease_expiration_date
      build.leasee = auth.get_current_identity()
      build.regenerate_lease_key()
    build.put()
    return build

  def get(self, build_id):
    """Gets a build by |build_id|.

    Requires the current user to have permissions to view the build.
    """
    build = model.Build.get_by_id(build_id)
    if not build:
      return None
    if not acl.current_user().can_view_build(build):
      raise auth.AuthorizationError()
    return build

  def peek(self, namespaces, max_builds=None):
    """Returns builds available for leasing in the specified |namespaces|.

    Builds are sorted by creation time, oldest first.

    Args:
      namespaces (list of string): fetch only builds in any of |namespaces|.
      max_builds (int): maximum number of builds to return. Defaults to 10.

    Returns:
      A list of Builds.
    """
    assert isinstance(namespaces, list)
    assert namespaces, 'No namespaces specified'
    assert all(isinstance(n, basestring) for n in namespaces), (
        'namespaces must be strings'
    )
    max_builds = max_builds or 10
    assert isinstance(max_builds, int)
    assert max_builds <= MAX_PEEK_BUILDS, (
        'max_builds must not be greater than %s' % MAX_PEEK_BUILDS
    )
    acl_user = acl.current_user()
    for namespace in namespaces:
      if not acl_user.can_peek_namespace(namespace):
        raise auth.AuthorizationError(
            'User %s cannot peek builds in namespace %s' %
            (acl_user, namespace))

    q = model.Build.query(
        model.Build.status == model.BuildStatus.SCHEDULED,
        model.Build.is_leased == False,
        model.Build.namespace.IN(namespaces),
    )
    q = q.order(model.Build.create_time) # oldest first.

    # Check once again locally because an ndb query may return an entity not
    # satisfying the query.
    builds = (b for b in q.iter()
              if (b.status == model.BuildStatus.SCHEDULED and
                  not b.is_leased and
                  b.namespace in namespaces and
                  acl_user.can_view_build(b))
             )
    builds = list(itertools.islice(builds, max_builds))
    builds = sorted(builds, key=lambda b: b.create_time)
    return builds

  def _get_leasable_build(self, build_id):
    build = model.Build.get_by_id(build_id)
    if build is None:
      raise BuildNotFoundError()
    acl_user = acl.current_user()
    if not acl_user.can_lease_build(build):
      raise auth.AuthorizationError()
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

    @ndb.transactional
    def try_lease():
      build = self._get_leasable_build(build_id)

      if build.status != model.BuildStatus.SCHEDULED or build.is_leased:
        return False, build

      build.lease_expiration_date = lease_expiration_date
      build.regenerate_lease_key()
      build.leasee = auth.get_current_identity()
      build.put()
      return True, build

    return try_lease()

  def _check_lease(self, build, lease_key):
    if not build.is_leased:
      raise InvalidBuildStateError('Build %s is not leased.' % build.key.id())
    if lease_key != build.lease_key:
      raise InvalidInputError('lease_key is incorrect. '
                              'Your lease might be expired.')

  def _clear_lease(self, build):
    """Clears build's lease attributes."""
    build.lease_key = None
    build.lease_expiration_date = None
    build.leasee = None

  @ndb.transactional
  def unlease(self, build_id, lease_key):
    """Unleases the build and resets its state. Idempotent.

    Resets status, url and lease_key.

    Returns:
      The unleased Build.
    """
    validate_lease_key(lease_key)
    build = self._get_leasable_build(build_id)
    if build.lease_key is None:
      if build.status == model.BuildStatus.SCHEDULED:
        return build
      raise InvalidBuildStateError('Cannot unlease a non-leased build')
    self._check_lease(build, lease_key)
    build.status = model.BuildStatus.SCHEDULED
    self._clear_lease(build)
    build.url = None
    build.put()
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
      if build.url == url:
        return build
      raise InvalidBuildStateError('Build %s is already started' % build_id)
    elif build.status == model.BuildStatus.COMPLETED:
      raise InvalidBuildStateError('Cannot start a compelted build')
    assert build.status == model.BuildStatus.SCHEDULED
    self._check_lease(build, lease_key)

    build.status = model.BuildStatus.STARTED
    build.url = url
    build.put()
    self._enqueue_callback_task_if_needed(build)
    return build

  @ndb.transactional
  def heartbeat(self, build_id, lease_key, lease_expiration_date):
    """Extends build lease.

    Args:
      build_id: id of the build.
      lease_key: current lease key.
      lease_expiration_date (datetime.timedelta): new lease expiration date.

    Returns:
      The updated Build.
    """
    validate_lease_key(lease_key)
    if lease_expiration_date is None:
      raise InvalidInputError('Lease expiration date not specified')
    validate_lease_expiration_date(lease_expiration_date)
    build = self._get_leasable_build(build_id)
    self._check_lease(build, lease_key)
    build.lease_expiration_date = lease_expiration_date
    build.put()
    return build

  @ndb.transactional
  def _complete(self, build_id, lease_key, result, failure_reason=None):
    """Marks a build as completed. Used by succeed and fail methods."""
    validate_lease_key(lease_key)
    assert result in (model.BuildResult.SUCCESS, model.BuildResult.FAILURE)
    build = self._get_leasable_build(build_id)

    if build.status == model.BuildStatus.COMPLETED:
      if build.result == result and build.failure_reason == failure_reason:
        return build
      raise InvalidBuildStateError('Build %s has already completed' % build_id)
    elif build.status != model.BuildStatus.STARTED:
      raise InvalidBuildStateError(
          'Cannot mark a non-started build as completed')
    self._check_lease(build, lease_key)

    build.status = model.BuildStatus.COMPLETED
    build.result = result
    build.failure_reason = failure_reason
    self._clear_lease(build)
    build.put()
    self._enqueue_callback_task_if_needed(build)
    return build

  def succeed(self, build_id, lease_key):
    """Marks a build as succeeded. Idempotent.

    Args:
      build_id: id of the build to complete.
      lease_key: current lease key.

    Returns:
      The succeeded Build.
    """
    return self._complete(build_id, lease_key, model.BuildResult.SUCCESS)

  def fail(self, build_id, lease_key, failure_reason=None):
    """Marks a build as failed. Idempotent.

    Args:
      build_id: id of the build to complete.
      lease_key: current lease key.
      failure_reason (model.FailureReason): why the build failed.
        Defaults to model.FailureReason.BUILD_FAILURE.

    Returns:
      The failed Build.
    """
    failure_reason = failure_reason or model.FailureReason.BUILD_FAILURE
    return self._complete(
        build_id, lease_key, model.BuildResult.FAILURE, failure_reason)

  @ndb.transactional
  def cancel(self, build_id):
    """Cancels build. Does not require a lease key.

    The current user has to have a permission to cancel a build in the
    build namespace.

    Returns:
      Canceled Build.
    """
    build = model.Build.get_by_id(build_id)
    if build is None:
      raise BuildNotFoundError()
    acl_user = acl.current_user()
    if not acl_user.can_cancel_build(build):
      raise auth.AuthorizationError()
    if build.status == model.BuildStatus.COMPLETED:
      if build.result == model.BuildResult.CANCELED:
        return build
      raise InvalidBuildStateError('Cannot cancel a completed build')
    build.status = model.BuildStatus.COMPLETED
    build.result = model.BuildResult.CANCELED
    build.cancelation_reason = model.CancelationReason.CANCELED_EXPLICITLY
    self._clear_lease(build)
    build.put()
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
        logging.info('Reset expired build %s successfully' % key.id())
