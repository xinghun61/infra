# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Access control list implementation.

Each bucket has its own ACL, stored in BucketAcl entity. Each entity has a list
of rules, where rule is a tuple (role, group). Possible roles are:
  * READER - has read-only access to a bucket.
  * SCHEDULER - same as READER + can schedule and cancel builds.
  * WRITER - same as SCHEDULER + can lease, mark as started and completed.
  * OWNER - same as WRITER + can change ACLs and can reset a build.
"""

import collections
import logging
import re

from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop
from components import auth
from components import utils
from protorpc import messages

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


class Role(messages.Enum):
  # Has read-only access to a bucket.
  READER = 1
  # Same as READER + can schedule and cancel builds.
  SCHEDULER = 2
  # Same as SCHEDULER + can lease, mark as started and completed.
  WRITER = 3
  # Same as WRITER + can change ACLs and can reset a build.
  OWNER = 4


_role_dict = Role.to_dict()


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
]
OWNER_ROLE_ACTIONS = WRITER_ROLE_ACTIONS + [
    Action.READ_ACL,
    Action.WRITE_ACL,
    Action.RESET_BUILD,
]


ACTIONS_FOR_ROLE = {
    Role.READER: set(READER_ROLE_ACTIONS),
    Role.SCHEDULER: set(SCHEDULER_ROLE_ACTIONS),
    Role.WRITER: set(WRITER_ROLE_ACTIONS),
    Role.OWNER: set(OWNER_ROLE_ACTIONS),
}


ROLES_FOR_ACTION = {
    a: set(r for r, actions in ACTIONS_FOR_ROLE.items() if a in actions)
    for a in Action
}


################################################################################
## Validation.


validate_bucket_name = errors.validate_bucket_name


def validate_group_name(group):
  """Raises errors.InvalidInputError if |group| is invalid."""
  if not auth.is_valid_group_name(group):
    raise errors.InvalidInputError('Invalid group "%s"' % group)


def validate_acl(acl):
  assert isinstance(acl, BucketAcl)
  for rule in acl.rules:
    validate_group_name(rule.group)


################################################################################
## Granular actions. API uses these.

def can_fn(action):
  assert isinstance(action, Action)
  return lambda bucket, identity=None: can(bucket, action, identity)


def can_fn_for_build(action):
  assert isinstance(action, Action)
  return lambda build, identity=None: can(build.bucket, action, identity)


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


def get_acl(bucket):
  """Returns ACL of |bucket|."""
  validate_bucket_name(bucket)
  if not can_read_acl(bucket):
    raise auth.AuthorizationError()
  return BucketAcl.get_by_id(bucket)


def set_acl(bucket, acl):
  """Overwrites ACL of |bucket|."""
  validate_bucket_name(bucket)
  validate_acl(acl)
  if not can_write_acl(bucket):
    raise auth.AuthorizationError()
  current_identity = auth.get_current_identity()
  logging.info(
      ('%s is changing ACLs of bucket %s to %r' %
       (current_identity.to_bytes(), bucket, acl.rules)))
  # Rely on BucketAcl._pre_put_hook validation.
  acl.key = ndb.Key(BucketAcl, bucket)
  acl.modified_by = current_identity
  acl.modified_time = utils.utcnow()
  acl.put()  # Overwrite.
  return acl


################################################################################
## Implementation.


class Rule(ndb.Model):
  """A tuple of role and group.

  Stored inside BucketAcl.
  """
  role = msgprop.EnumProperty(Role, required=True)
  group = ndb.StringProperty(required=True)


class BucketAcl(ndb.Model):
  """Stores ACL rules.

  Entity key:
    Id is a bucket name. Has no parent.
  """
  # Ordered list of ACL rules. Each rule is a role name and group.
  rules = ndb.StructuredProperty(Rule, repeated=True)
  # Who made the last change.
  modified_by = auth.IdentityProperty(indexed=True, required=True)
  # When the last change was made.
  modified_time = ndb.DateTimeProperty(indexed=True, required=True)

  @property
  def bucket(self):
    return self.key.string_id()

  def _pre_put_hook(self):
    validate_bucket_name(self.bucket)
    for rule in self.rules:
      validate_group_name(rule.group)


@ndb.non_transactional
def has_any_of_roles(bucket, roles, identity=None):
  """True if |identity| has any of |roles| in |bucket|."""
  validate_bucket_name(bucket)
  for r in roles:
    assert isinstance(r, Role)
  identity = identity or auth.get_current_identity()

  if auth.is_admin(identity):
    return True

  roles = set(roles)
  bucket_acl = BucketAcl.get_by_id(bucket)
  if bucket_acl:
    for rule in bucket_acl.rules:
      if rule.role in roles and auth.is_group_member(rule.group, identity):
        return True
  return False


def can(bucket, action, identity=None):
  validate_bucket_name(bucket)
  assert isinstance(action, Action)
  return has_any_of_roles(bucket, ROLES_FOR_ACTION[action], identity)


def get_available_buckets(identity=None):
  """Returns buckets available to the |identity|.

  Results are memcached for 10 minutes per identity.

  Returns:
    Set of bucket names or None if all buckets are available.
  """
  identity = identity or auth.get_current_identity()
  if auth.is_admin(identity):
    return None

  cache_key = 'available_buckets/%s' % identity.to_bytes()
  available_buckets = memcache.get(cache_key)
  if available_buckets is not None:
    return available_buckets
  logging.info(
      'Computing a list of available buckets for %s' % identity.to_bytes())
  group_buckets_map = collections.defaultdict(set)
  for acl in BucketAcl.query().iter():
    for rule in acl.rules:
      group_buckets_map[rule.group].add(acl.bucket)
  available_buckets = set()
  for group, buckets in group_buckets_map.iteritems():
    if available_buckets.issuperset(buckets):
      continue
    if auth.is_group_member(group, identity):
      available_buckets.update(buckets)
  # Cache for 10 min
  memcache.add(cache_key, available_buckets, 10 * 60)
  return available_buckets
