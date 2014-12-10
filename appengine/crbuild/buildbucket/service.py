# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import itertools
import json

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from components import auth
from . import model
import acl


MAX_PEEK_BUILDS = 100
MAX_LEASE_DURATION = datetime.timedelta(hours=3)


class BuildNotFoundError(Exception):
  pass


class StatusIsFinalError(Exception):
  pass


class BadLeaseKeyError(Exception):
  pass


class BuildBucketService(object):
  def add(self, build):
    """Adds the build entity to the build bucket.

    Requires the current user to have permissions add to builds to the
    |build.namespace| namespace.
    """
    assert build
    assert build.namespace
    acl_user = acl.current_user()
    if not acl_user.can_add_build_to_namespace(build.namespace):
      raise auth.AuthorizationError('namespace %s is not allowed for %s' %
                                    (build.namespace, acl_user))
    build.put()

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

  def peek(self, namespaces, max_builds=10):
    """Returns builds available for leasing in the specified |namespaces|.

    Builds are sorted by available_since attribute, oldest first.

    Args:
      namespaces (list of string): fetch only builds in any of |namespaces|.
      max_builds (int): maximum number of builds to return.

    Returns:
      A list of Builds.
    """
    assert isinstance(namespaces, list)
    assert namespaces, 'No namespaces specified'
    assert all(isinstance(n, basestring) for n in namespaces), (
        'namespaces must be strings'
    )
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

    # This predicate must be in sync with Build.is_leasable()
    q = model.Build.query(
        model.Build.status.IN(model.LEASABLE_STATUSES),
        model.Build.namespace.IN(namespaces),
        model.Build.available_since <= datetime.datetime.utcnow(),
    )
    q = q.order(model.Build.available_since) # oldest first.

    # Check once again locally because an ndb query may return an entity not
    # satisfying the query. Assume build namespace never changes.
    builds = (b for b in q.iter()
              if b.is_leasable() and acl_user.can_view_build(b))
    builds = list(itertools.islice(builds, max_builds))
    builds = sorted(builds, key=lambda b: b.available_since)
    return builds

  def lease(self, build_id, duration=None):
    """Leases the build, makes it unavailable for the lease duration.

    After the lease expires, the build can be leased again.
    Changes lease_key to a different value.

    Args:
      build_id (int): build id.
      duration (datetime.timedelta): lease duration. Defaults to 10 seonds.

    Returns:
      Tuple:
        success (bool): True if the build was leased
        build (ndb.Build)
    """
    if duration is None:
      duration = datetime.timedelta(seconds=10)
    assert isinstance(duration, datetime.timedelta)
    assert duration < MAX_LEASE_DURATION, (
        'duration must not exceed %s' % MAX_LEASE_DURATION
    )

    acl_user = acl.current_user()
    new_available_since = datetime.datetime.utcnow() + duration

    @ndb.transactional
    def try_lease():
      build = model.Build.get_by_id(build_id)
      if not build:
        raise BuildNotFoundError()
      if not acl_user.can_lease_build(build):
        raise auth.AuthorizationError(
            'User %s cannot lease build %s' % (acl_user, build_id))

      if not build.is_leasable():
        return False, build

      build.available_since = new_available_since
      build.regenerate_lease_key()
      build.put()
      return True, build

    return try_lease()

  @staticmethod
  def _enqueue_callback_task(build):
    assert ndb.in_transaction()
    assert build
    assert build.callback
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

  def update(self, build_id, lease_key=None, lease_duration=None, url=None,
             status=None):
    """Updates build properties.

    Args:
      build_id (int): id of the build.
      lease_key (int): lease key obtained from calling BuildBucketService.lease.
        The lease_key must match current build lease key. If the build is not
        leased, the current lease key is None.
      lease_duration (datetime.timedelta): if not None, new value of lease
        duration. Defaults to None.
      url (str): if not None, new value of build url. Defaults to None.
      status (model.BuildStatus): if not None, the new value of build status.
        Defaults to None.
    """
    assert lease_key is None or isinstance(lease_key, int)
    assert (lease_duration is None or
            isinstance(lease_duration, datetime.timedelta))
    assert url is None or isinstance(url, basestring)
    assert status is None or isinstance(status, model.BuildStatus)

    unlease = lease_duration is not None and not lease_duration
    new_available_since = None
    if lease_duration is not None:
      new_available_since = datetime.datetime.utcnow() + lease_duration

    @ndb.transactional
    def do_update():
      build = model.Build.get_by_id(build_id)
      if build is None:
        raise BuildNotFoundError()
      acl_user = acl.current_user()
      if not acl_user.can_lease_build(build):
        raise auth.AuthorizationError()
      if build.lease_key is not None and lease_key != build.lease_key:
        raise BadLeaseKeyError('lease_key is incorrect. '
                               'Your lease might be expired.')

      if url is not None:
        build.url = url

      if new_available_since:
        build.available_since = new_available_since
        if unlease:  # pragma: no branch
          build.lease_key = None

      status_change = False
      if status is not None and build.status != status:
        if build.is_status_final():
          raise StatusIsFinalError(
              'Build status cannot be changed from status %s' % build.status)
        build.status = status
        status_change = True

      build.put()

      if status_change and build.callback:
        self._enqueue_callback_task(build)
    return do_update()
