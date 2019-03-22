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
from google.appengine.ext import ndb

from components import auth
from components import utils

from protorpc import messages
from proto.config import project_config_pb2
import config
import errors

# Group whitelisting users to update builds. They are expected to be robots.
UPDATE_BUILD_ALLOWED_USERS = 'buildbucket-update-build-users'

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
  return lambda build: can_async(build.bucket_id, action)


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


@ndb.tasklet
def can_update_build_async():  # pragma: no cover
  """Returns if the current identity is whitelisted to update builds."""
  raise ndb.Return(auth.is_group_member(UPDATE_BUILD_ALLOWED_USERS))


################################################################################
## Implementation.


def get_role_async(bucket_id, identity=None):
  """Returns the most permissive role of the given user in |bucket_id|.

  The most permissive role is the role that allows most actions, e.g. WRITER
  is more permissive than READER.

  Returns None if there's no such bucket or the given identity has no roles in
  it at all.
  """
  config.validate_bucket_id(bucket_id)

  identity = identity or auth.get_current_identity()
  assert isinstance(identity, auth.Identity), identity
  identity_str = identity.to_bytes()

  @ndb.tasklet
  def impl():
    ctx = ndb.get_context()
    cache_key = 'role/%s/%s' % (identity_str, bucket_id)
    cache = yield ctx.memcache_get(cache_key)
    if cache is not None:
      raise ndb.Return(cache[0])

    _, bucket_cfg = yield config.get_bucket_async(bucket_id)
    if not bucket_cfg:
      raise ndb.Return(None)
    if auth.is_admin(identity):
      raise ndb.Return(project_config_pb2.Acl.WRITER)

    # A LUCI service calling us in the context of some project is allowed to
    # do anything it wants in that project. We trust all LUCI services to do
    # authorization on their own for this case. A cross-project request must be
    # explicitly authorized in Buildbucket ACLs though (so we proceed to the
    # bucket_cfg check below).
    if identity.is_project:
      project_id, _ = config.parse_bucket_id(bucket_id)
      if project_id == identity.name:
        logging.debug(
            'crbug.com/938083: access to %s is authorized via X-Luci-Project',
            bucket_id
        )
        raise ndb.Return(project_config_pb2.Acl.WRITER)

    # Roles are just numbers. The higher the number, the more permissions
    # the identity has. We exploit this here to get the single maximally
    # permissive role for the current identity.
    role = None
    for rule in bucket_cfg.acls:
      if rule.role <= role:
        continue
      if (rule.identity == identity_str or
          (rule.group and auth.is_group_member(rule.group, identity))):
        role = rule.role
    yield ctx.memcache_set(cache_key, (role,), time=60)
    raise ndb.Return(role)

  return _get_or_create_cached_future(identity, 'role/%s' % bucket_id, impl)


@ndb.tasklet
def can_async(bucket_id, action):
  config.validate_bucket_id(bucket_id)
  assert isinstance(action, Action)
  min_role = ACTION_TO_MIN_ROLE[action]

  identity = auth.get_current_identity()
  role = yield get_role_async(bucket_id, identity)
  if role is not None and role >= min_role:
    raise ndb.Return(True)

  # TODO(crbug.com/938083): Temporary fallback to checking that the immediate
  # peer (e.g. LUCI Scheduler own account) has the role, to avoid breaking
  # everything during the migration period.
  if identity.is_project:
    role = yield get_role_async(bucket_id, auth.get_peer_identity())
    if role is not None and role >= min_role:
      logging.warning(
          'crbug.com/938083: %s should have role %d in %s' %
          (identity.to_bytes(), role, bucket_id)
      )
      raise ndb.Return(True)

  raise ndb.Return(False)


def get_accessible_buckets_async():
  """Returns buckets accessible to the current identity.

  A bucket is accessible if the requester has ACCESS_BUCKET permission.

  Results are memcached for 10 minutes per identity.

  Returns:
    A future of
      a set of bucket ids strings
      or None if all buckets are available.
  """

  # TODO(vadimsh): This function doesn't understand 'project:...' identities.

  @ndb.tasklet
  def impl():
    if auth.is_admin():
      raise ndb.Return(None)

    identity = auth.get_current_identity().to_bytes()
    cache_key = 'accessible_buckets_v2/%s' % identity
    ctx = ndb.get_context()
    available_buckets = yield ctx.memcache_get(cache_key)
    if available_buckets is not None:
      raise ndb.Return(available_buckets)
    logging.info('Computing a list of available buckets for %s' % identity)
    group_buckets_map = collections.defaultdict(set)
    available_buckets = set()
    all_buckets = yield config.get_buckets_async()

    for bucket_id, cfg in all_buckets.iteritems():
      for rule in cfg.acls:
        if rule.identity == identity:
          available_buckets.add(bucket_id)
        elif rule.group:  # pragma: no branch
          group_buckets_map[rule.group].add(bucket_id)

    for group, buckets in group_buckets_map.iteritems():
      if available_buckets.issuperset(buckets):
        continue
      if auth.is_group_member(group):
        available_buckets.update(buckets)
    # Cache for 10 min
    yield ctx.memcache_set(cache_key, available_buckets, 10 * 60)
    raise ndb.Return(available_buckets)

  return _get_or_create_cached_future(
      auth.get_current_identity(), 'accessible_buckets', impl
  )


@utils.cache
def self_identity():  # pragma: no cover
  """Returns identity of the buildbucket app."""
  return auth.Identity('user', app_identity.get_service_account_name())


def delegate_async(target_service_host, identity=None, tag=''):
  """Mints a delegation token for the current identity."""
  tag = tag or ''
  identity = identity or auth.get_current_identity()

  # TODO(vadimsh): 'identity' here can be 'project:<...>' and we happily create
  # a delegation token for it, which is weird. Buildbucket should call Swarming
  # using 'project:<...>' identity directly, not through a delegation token.

  def impl():
    return auth.delegate_async(
        audience=[self_identity()],
        services=['https://%s' % target_service_host],
        impersonate=identity,
        tags=[tag] if tag else [],
    )

  return _get_or_create_cached_future(
      identity, 'delegation_token:%s:%s' % (target_service_host, tag), impl
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


def _get_or_create_cached_future(identity, key, create_future):
  """Returns a future cached in the current GAE request context.

  Uses the pair (identity, key) as the caching key.

  Using this function may cause RuntimeError with a deadlock if the returned
  future is not waited for before leaving an ndb context, but that's a bug
  in the first place.
  """
  assert isinstance(identity, auth.Identity), identity
  full_key = (identity, key)

  # Docs:
  # https://cloud.google.com/appengine/docs/standard/python/how-requests-are-handled#request-ids
  req_id = os.environ['REQUEST_LOG_ID']
  cache = getattr(_thread_local, 'request_cache', {})
  if cache.get('request_id') != req_id:
    cache = {
        'request_id': req_id,
        'futures': {},
    }
    _thread_local.request_cache = cache

  fut_entry = cache['futures'].get(full_key)
  if fut_entry is None:
    fut_entry = {
        'future': create_future(),
        'ndb_context': ndb.get_context(),
    }
    cache['futures'][full_key] = fut_entry
  assert (
      fut_entry['future'].done() or
      ndb.get_context() is fut_entry['ndb_context']
  )
  return fut_entry['future']


def clear_request_cache():
  _thread_local.request_cache = {}
