# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""User-related functions, including access control list implementation.

See Acl message in proto/project_config.proto.
"""

import collections
import logging
import os
import threading

from google.appengine.api import app_identity
from google.appengine.api import memcache
from google.appengine.ext import ndb

from components import auth
from components import utils

from protorpc import messages
from proto.config import project_config_pb2
import config
import errors

################################################################################
## Role definitions.


class Action(messages.Enum):
  # Schedule a build.
  ADD_BUILD = 1
  # Get information about a build.
  VIEW_BUILD = 2
  # Lease a build for execution. Normally done by build systems.
  LEASE_BUILD = 3
  # Cancel an existing build. Does not require a lease key.
  CANCEL_BUILD = 4
  # Unlease and reset state of an existing build. Normally done by admins.
  RESET_BUILD = 5
  # Search for builds or get a list of scheduled builds.
  SEARCH_BUILDS = 6
  # Delete all scheduled builds from a bucket.
  DELETE_SCHEDULED_BUILDS = 9
  # Know about bucket existence and read its info.
  ACCESS_BUCKET = 10
  # Pause builds for a given bucket.
  PAUSE_BUCKET = 11
  # Set the number for the next build in a builder.
  SET_NEXT_NUMBER = 12


_action_dict = Action.to_dict()

# Maps an Action to a description.
ACTION_DESCRIPTIONS = {
    Action.ADD_BUILD:
        'Schedule a build.',
    Action.VIEW_BUILD:
        'Get information about a build.',
    Action.LEASE_BUILD:
        'Lease a build for execution.',
    Action.CANCEL_BUILD:
        'Cancel an existing build. Does not require a lease key.',
    Action.RESET_BUILD:
        'Unlease and reset state of an existing build.',
    Action.SEARCH_BUILDS:
        'Search for builds or get a list of scheduled builds.',
    Action.DELETE_SCHEDULED_BUILDS:
        'Delete all scheduled builds from a bucket.',
    Action.ACCESS_BUCKET:
        'Know about a bucket\'s existence and read its info.',
    Action.PAUSE_BUCKET:
        'Pause builds for a given bucket.',
    Action.SET_NEXT_NUMBER:
        'Set the number for the next build in a builder.',
}
# Maps a project_config_pb2.Acl.Role to a description.
ROLE_DESCRIPTIONS = {
    project_config_pb2.Acl.READER:
        'Can do read-only operations, such as search for builds.',
    project_config_pb2.Acl.SCHEDULER:
        'Same as READER + can schedule and cancel builds.',
    project_config_pb2.Acl.WRITER:
        'Can do all write operations.',
}

# Maps an Action to a minimum project_config_pb2.Acl.Role required for the
# action.
ACTION_TO_MIN_ROLE = {
    # Reader.
    Action.ACCESS_BUCKET: project_config_pb2.Acl.READER,
    Action.VIEW_BUILD: project_config_pb2.Acl.READER,
    Action.SEARCH_BUILDS: project_config_pb2.Acl.READER,
    # Scheduler.
    Action.ADD_BUILD: project_config_pb2.Acl.SCHEDULER,
    Action.CANCEL_BUILD: project_config_pb2.Acl.SCHEDULER,
    # Writer.
    Action.LEASE_BUILD: project_config_pb2.Acl.WRITER,
    Action.RESET_BUILD: project_config_pb2.Acl.WRITER,
    Action.DELETE_SCHEDULED_BUILDS: project_config_pb2.Acl.WRITER,
    Action.PAUSE_BUCKET: project_config_pb2.Acl.WRITER,
    Action.SET_NEXT_NUMBER: project_config_pb2.Acl.WRITER,
}

# Maps a project_config_pb2.Acl.Role to a set of permitted Actions.
ROLE_TO_ACTIONS = {
    r: {a for a, mr in ACTION_TO_MIN_ROLE.iteritems() if r >= mr
       } for r in project_config_pb2.Acl.Role.values()
}

################################################################################
## Granular actions. API uses these.


def can_async_fn(action):
  assert isinstance(action, Action)
  return lambda bucket: can_async(bucket, action)  # pragma: no cover


def can_async_fn_for_build(action):
  assert isinstance(action, Action)
  return lambda build: can_async(build.bucket, action)


# Functions for each Action.
# Some accept build as first param, others accept bucket name.
can_view_build_async = can_async_fn_for_build(Action.VIEW_BUILD)
can_search_builds_async = can_async_fn(Action.SEARCH_BUILDS)
can_add_build_async = can_async_fn(Action.ADD_BUILD)
can_lease_build_async = can_async_fn_for_build(Action.LEASE_BUILD)
can_cancel_build_async = can_async_fn_for_build(Action.CANCEL_BUILD)
can_reset_build_async = can_async_fn_for_build(Action.RESET_BUILD)
can_delete_scheduled_builds_async = can_async_fn(Action.DELETE_SCHEDULED_BUILDS)
can_pause_buckets_async = can_async_fn(Action.PAUSE_BUCKET)
can_access_bucket_async = can_async_fn(Action.ACCESS_BUCKET)
can_set_next_number_async = can_async_fn(Action.SET_NEXT_NUMBER)

################################################################################
## Implementation.


def get_role_async(bucket):
  """Returns the most permissive role of the current identity in |bucket|.

  The most permissive role is the role that allows most actions, e.g. WRITER
  is more permissive than READER.
  """
  errors.validate_bucket_name(bucket)

  @ndb.tasklet
  def impl():
    ctx = ndb.get_context()
    identity_str = auth.get_current_identity().to_bytes()
    cache_key = 'role/%s/%s' % (identity_str, bucket)
    cache = yield ctx.memcache_get(cache_key)
    if cache is not None:
      raise ndb.Return(cache[0])

    _, bucket_cfg = yield config.get_bucket_async(bucket)
    if not bucket_cfg:
      raise ndb.Return(None)
    if auth.is_admin():
      raise ndb.Return(project_config_pb2.Acl.WRITER)

    # Roles are just numbers. The higher the number, the more permissions
    # the identity has. We exploit this here to get the single maximally
    # permissive role for the current identity.
    role = None
    for rule in bucket_cfg.acls:
      if rule.role <= role:
        continue
      if (rule.identity == identity_str or
          (rule.group and auth.is_group_member(rule.group))):
        role = rule.role
    yield ctx.memcache_set(cache_key, (role,), time=60)
    raise ndb.Return(role)

  return _get_or_create_cached_future('role/%s' % bucket, impl)


@ndb.tasklet
def can_async(bucket, action):
  errors.validate_bucket_name(bucket)
  assert isinstance(action, Action)

  role = yield get_role_async(bucket)
  raise ndb.Return(role is not None and role >= ACTION_TO_MIN_ROLE[action])


def get_acessible_buckets_async():
  """Returns buckets accessible to the current identity.

  A bucket is accessible if the requester has ACCESS_BUCKET permission.

  Results are memcached for 10 minutes per identity.

  Returns:
    A future of a set of bucket names or None if all buckets are available.
  """

  @ndb.tasklet
  def impl():
    if auth.is_admin():
      raise ndb.Return(None)

    identity = auth.get_current_identity().to_bytes()
    cache_key = 'available_buckets/%s' % identity
    ctx = ndb.get_context()
    available_buckets = yield ctx.memcache_get(cache_key)
    if available_buckets is not None:
      raise ndb.Return(available_buckets)
    logging.info('Computing a list of available buckets for %s' % identity)
    group_buckets_map = collections.defaultdict(set)
    available_buckets = set()
    all_buckets = yield config.get_buckets_async()
    for _, bucket in all_buckets:
      for rule in bucket.acls:
        if rule.identity == identity:
          available_buckets.add(bucket.name)
        if rule.group:
          group_buckets_map[rule.group].add(bucket.name)
    for group, buckets in group_buckets_map.iteritems():
      if available_buckets.issuperset(buckets):
        continue
      if auth.is_group_member(group):
        available_buckets.update(buckets)
    # Cache for 10 min
    yield ctx.memcache_set(cache_key, available_buckets, 10 * 60)
    raise ndb.Return(available_buckets)

  return _get_or_create_cached_future('accessible_buckets', impl)


@utils.cache
def self_identity():  # pramga: no cover
  """Returns identity of the buildbucket app."""
  return auth.Identity('user', app_identity.get_service_account_name())


def delegate_async(target_service_host, tag=''):
  """Mints a delegation token for the current identity."""
  tag = tag or ''

  def impl():
    return auth.delegate_async(
        audience=[self_identity()],
        services=['https://%s' % target_service_host],
        impersonate=auth.get_current_identity(),
        tags=[tag] if tag else [],
    )

  return _get_or_create_cached_future(
      'delegation_token:%s:%s' % (target_service_host, tag), impl
  )


def current_identity_cannot(action_format, *args):  # pragma: no cover
  """Returns AuthorizationError."""
  action = action_format % args
  msg = 'User %s cannot %s' % (auth.get_current_identity().to_bytes(), action)
  logging.warning(msg)
  return auth.AuthorizationError(msg)


def parse_identity(identity):
  """Parses an identity string if it is a string."""
  if isinstance(identity, basestring):
    if not identity:  # pragma: no cover
      return None
    if ':' not in identity:  # pragma: no branch
      identity = 'user:%s' % identity
    try:
      identity = auth.Identity.from_bytes(identity)
    except ValueError as ex:
      raise errors.InvalidInputError('Invalid identity: %s' % ex)
  return identity


_thread_local = threading.local()


def _get_or_create_cached_future(key, create_future):
  """Returns a future cached for the current GAE request.

  Using this function may cause RuntimeError with a deadlock if the returned
  future is not waited for before leaving an ndb context, but that's a bug
  in the first place.
  """
  # Docs:
  # https://cloud.google.com/appengine/docs/standard/python/how-requests-are-handled#request-ids
  req_id = os.environ['REQUEST_LOG_ID']
  cache = getattr(_thread_local, 'request_cache', {})
  if cache.get('request_id') != req_id:
    cache = {
        'request_id': req_id,
        'futures': {},
        'current_identity': auth.get_current_identity(),
    }
    _thread_local.request_cache = cache
  assert cache['current_identity'] == auth.get_current_identity()

  fut_entry = cache['futures'].get(key)
  if fut_entry is None:
    fut_entry = {
        'future': create_future(),
        'ndb_context': ndb.get_context(),
    }
    cache['futures'][key] = fut_entry
  assert (
      fut_entry['future'].done() or
      ndb.get_context() is fut_entry['ndb_context']
  )
  return fut_entry['future']


def clear_request_cache():
  _thread_local.request_cache = {}
