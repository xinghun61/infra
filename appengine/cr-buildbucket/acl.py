# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Access control list implementation.

See Acl message in proto/project_config.proto.
"""

import collections
import logging
from google.appengine.api import memcache
from google.appengine.ext import ndb
from components import auth
from protorpc import messages
from proto import project_config_pb2
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
  # View bucket ACLs.
  READ_ACL = 7
  # Change bucket ACLs.
  WRITE_ACL = 8
  # Delete all scheduled builds from a bucket.
  DELETE_SCHEDULED_BUILDS = 9
  # Know about bucket existence and read its info.
  ACCESS_BUCKET = 10
  # Pause builds for a given bucket.
  PAUSE_BUCKET = 11
  # Set the number for the next build in a builder.
  SET_NEXT_NUMBER = 12


_action_dict = Action.to_dict()

ACTION_DESCRIPTIONS = {
  Action.ADD_BUILD: 'Schedule a build.',
  Action.VIEW_BUILD: 'Get information about a build.',
  Action.LEASE_BUILD: 'Lease a build for execution.',
  Action.CANCEL_BUILD:
    'Cancel an existing build. Does not require a lease key.',
  Action.RESET_BUILD: 'Unlease and reset state of an existing build.',
  Action.SEARCH_BUILDS: 'Search for builds or get a list of scheduled builds.',
  Action.READ_ACL: 'View bucket ACLs.',
  Action.WRITE_ACL: 'Change bucket ACLs.',
  Action.DELETE_SCHEDULED_BUILDS: 'Delete all scheduled builds from a bucket.',
  Action.ACCESS_BUCKET: 'Know about a bucket\'s existence and read its info.',
  Action.PAUSE_BUCKET: 'Pause builds for a given bucket.',
  Action.SET_NEXT_NUMBER: 'Set the number for the next build in a builder.',
}
READER_ROLE_ACTIONS = [
  Action.ACCESS_BUCKET,
  Action.VIEW_BUILD,
  Action.SEARCH_BUILDS,
]
SCHEDULER_ROLE_ACTIONS = READER_ROLE_ACTIONS + [
  Action.ADD_BUILD,
  Action.CANCEL_BUILD,
]
WRITER_ROLE_ACTIONS = SCHEDULER_ROLE_ACTIONS + [
  Action.LEASE_BUILD,
  Action.RESET_BUILD,
  Action.DELETE_SCHEDULED_BUILDS,
  Action.PAUSE_BUCKET,
  Action.SET_NEXT_NUMBER,
]
ROLE_DESCRIPTIONS = {
  project_config_pb2.Acl.READER:
    'Can do read-only operations, such as search for builds.',
  project_config_pb2.Acl.SCHEDULER:
    'Same as READER + can schedule and cancel builds.',
  project_config_pb2.Acl.WRITER: 'Can do all write operations.',
}
ACTIONS_FOR_ROLE = {
  project_config_pb2.Acl.READER: set(READER_ROLE_ACTIONS),
  project_config_pb2.Acl.SCHEDULER: set(SCHEDULER_ROLE_ACTIONS),
  project_config_pb2.Acl.WRITER: set(WRITER_ROLE_ACTIONS),
}
ROLES_FOR_ACTION = {
  a: set(r for r, actions in ACTIONS_FOR_ROLE.items() if a in actions)
  for a in Action
}


################################################################################
## Granular actions. API uses these.

def can_fn(action):
  assert isinstance(action, Action)
  return lambda bucket: can(bucket, action)  # pragma: no cover


def can_fn_for_build(action):
  assert isinstance(action, Action)
  return lambda build: can(build.bucket, action)


# Functions for each Action.
# Some accept build as first param, others accept bucket name.
can_view_build = can_fn_for_build(Action.VIEW_BUILD)
can_search_builds = can_fn(Action.SEARCH_BUILDS)
can_add_build = can_fn(Action.ADD_BUILD)
can_add_build_async = lambda bucket: can_async(bucket, Action.ADD_BUILD)
can_lease_build = can_fn_for_build(Action.LEASE_BUILD)
can_cancel_build = can_fn_for_build(Action.CANCEL_BUILD)
can_reset_build = can_fn_for_build(Action.RESET_BUILD)
can_read_acl = can_fn(Action.READ_ACL)
can_write_acl = can_fn(Action.WRITE_ACL)
can_delete_scheduled_builds = can_fn(Action.DELETE_SCHEDULED_BUILDS)
can_pause_buckets = can_fn(Action.PAUSE_BUCKET)
can_access_bucket = can_fn(Action.ACCESS_BUCKET)
can_set_next_number = can_fn(Action.SET_NEXT_NUMBER)


################################################################################
## Implementation.


@ndb.tasklet
def get_role_async(bucket):
  """Returns the roles available for the current identity in |bucket|."""
  errors.validate_bucket_name(bucket)

  if auth.is_admin():
    raise ndb.Return(project_config_pb2.Acl.WRITER)

  _, bucket_cfg = yield config.get_bucket_async(bucket)
  identity_str = auth.get_current_identity().to_bytes()
  # Roles are just numbers, and the higher the number goes the more permissions
  # the identity has. We exploit this here to get the single maximally
  # permissive role for the current identity.
  role = None
  if bucket_cfg:
    for rule in bucket_cfg.acls:
      if rule.role <= role:
        continue
      if (rule.identity == identity_str or
          (rule.group and auth.is_group_member(rule.group))):
        role = rule.role
  raise ndb.Return(role)


@ndb.tasklet
def has_any_of_roles_async(bucket, roles):
  """True if current identity has any of |roles| in |bucket|."""
  assert roles
  errors.validate_bucket_name(bucket)
  roles = set(roles)
  assert roles.issubset(project_config_pb2.Acl.Role.values())

  if auth.is_admin():
    raise ndb.Return(True)

  _, bucket_cfg = yield config.get_bucket_async(bucket)
  identity_str = auth.get_current_identity().to_bytes()
  if bucket_cfg:
    for rule in bucket_cfg.acls:
      if rule.role not in roles:
        continue
      if rule.identity == identity_str:
        raise ndb.Return(True)
      if rule.group and auth.is_group_member(rule.group):
        raise ndb.Return(True)
  raise ndb.Return(False)


@ndb.tasklet
def can_async(bucket, action):
  errors.validate_bucket_name(bucket)
  assert isinstance(action, Action)

  identity = auth.get_current_identity()
  cache_key = 'acl_can/%s/%s/%s' % (bucket, identity.to_bytes(), action.name)
  ctx = ndb.get_context()
  result = yield ctx.memcache_get(cache_key)
  if result is not None:
    raise ndb.Return(result)

  result = yield has_any_of_roles_async(bucket, ROLES_FOR_ACTION[action])
  yield ctx.memcache_set(cache_key, result, time=60)
  raise ndb.Return(result)


def can(bucket, action):
  return can_async(bucket, action).get_result()


def get_available_buckets():
  """Returns buckets available to the current identity.

  Results are memcached for 10 minutes per identity.

  Returns:
    Set of bucket names or None if all buckets are available.
  """
  if auth.is_admin():
    return None

  identity = auth.get_current_identity().to_bytes()
  cache_key = 'available_buckets/%s' % identity
  available_buckets = memcache.get(cache_key)
  if available_buckets is not None:
    return available_buckets
  logging.info(
      'Computing a list of available buckets for %s' % identity)
  group_buckets_map = collections.defaultdict(set)
  available_buckets = set()
  all_buckets = config.get_buckets_async().get_result()
  for bucket in all_buckets:
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
  memcache.set(cache_key, available_buckets, 10 * 60)
  return available_buckets


def current_identity_cannot(action_format, *args):  # pragma: no cover
  """Returns AuthorizationError."""
  action = action_format % args
  msg = 'User %s cannot %s' % (auth.get_current_identity().to_bytes(), action)
  logging.warning(msg)
  return auth.AuthorizationError(msg)
