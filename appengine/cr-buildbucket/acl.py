# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Access control list implementation.

See Acl message in proto/project_config.proto.
"""

import collections
import logging

from google.appengine.api import memcache
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


_action_dict = Action.to_dict()


READER_ROLE_ACTIONS = [
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
]
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
can_lease_build = can_fn_for_build(Action.LEASE_BUILD)
can_cancel_build = can_fn_for_build(Action.CANCEL_BUILD)
can_reset_build = can_fn_for_build(Action.RESET_BUILD)
can_read_acl = can_fn(Action.READ_ACL)
can_write_acl = can_fn(Action.WRITE_ACL)


################################################################################
## Implementation.


def has_any_of_roles(bucket, roles):
  """True if current identity has any of |roles| in |bucket|."""
  assert bucket
  assert roles
  errors.validate_bucket_name(bucket)
  roles = set(roles)
  assert roles.issubset(project_config_pb2.Acl.Role.values())

  if auth.is_admin():
    return True

  bucket_cfg = config.get_bucket(bucket)
  identity_str = auth.get_current_identity().to_bytes()
  if bucket_cfg:
    for rule in bucket_cfg.acls:
      if rule.role not in roles:
        continue
      if rule.identity == identity_str:
        return True
      if rule.group and auth.is_group_member(rule.group):
        return True
  return False


def can(bucket, action):
  errors.validate_bucket_name(bucket)
  assert isinstance(action, Action)

  identity = auth.get_current_identity()
  cache_key = 'acl_can/%s/%s/%s' % (bucket, identity.to_bytes(), action.name)
  result = memcache.get(cache_key)
  if result is not None:
    return result

  result = has_any_of_roles(bucket, ROLES_FOR_ACTION[action])
  memcache.set(cache_key, result, time=60)
  return result


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
  for bucket in config.get_buckets():
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
