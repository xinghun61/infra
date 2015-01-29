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

from google.appengine.ext import ndb
from components import auth
from components import utils

import errors


################################################################################
## Role definitions.


READER_ROLE_ACTIONS = [
    'view_build',
    'search_builds',
]
SCHEDULER_ROLE_ACTIONS = READER_ROLE_ACTIONS + [
    'add_build',
    'cancel_build'
]
WRITER_ROLE_ACTIONS = SCHEDULER_ROLE_ACTIONS + [
   'lease_build'
]
OWNER_ROLE_ACTIONS = WRITER_ROLE_ACTIONS + [
    'read_acl',
    'write_acl',
    'reset_build',
]

ALL_ACTIONS = set(OWNER_ROLE_ACTIONS)

ROLES = {
    'READER': set(READER_ROLE_ACTIONS),
    'SCHEDULER': set(SCHEDULER_ROLE_ACTIONS),
    'WRITER': set(WRITER_ROLE_ACTIONS),
    'OWNER': set(OWNER_ROLE_ACTIONS),
}

ROLES_FOR_ACTION = {
    a: set(r for r, actions in ROLES.items() if a in actions)
    for a in ALL_ACTIONS
}


################################################################################
## Validation.


validate_bucket_name = errors.validate_bucket_name


def validate_role_name(role_name):
  """Raises errors.InvalidInputError if |role_name| is invalid."""
  if role_name not in ROLES:
    raise errors.InvalidInputError('Invalid role name "%s"' % role_name)


def validate_group_name(group):
  """Raises errors.InvalidInputError if |group| is invalid."""
  if not auth.is_valid_group_name(group):
    raise errors.InvalidInputError('Invalid group "%s"' % group)


def validate_action_name(action):
  """Raises errors.InvalidInputError if |action| is invalid."""
  if action not in ALL_ACTIONS:
    raise errors.InvalidInputError('Invalid action "%s"' % action)


################################################################################
## Granular actions. API uses these.

def can_fn(action):
  validate_action_name(action)
  return lambda bucket, identity=None: can(bucket, action, identity)


def can_fn_for_build(action):
  validate_action_name(action)
  return lambda build, identity=None: can(build.bucket, action, identity)


# Getting information about a build.
can_view_build = can_fn_for_build('view_build')
# Getting a list of scheduled builds.
can_search_builds = can_fn_for_build('search_builds')
# Scheduling a build.
can_add_build = can_fn('add_build')
# Leasing a build for running. Normally done by build systems.
can_lease_build = can_fn_for_build('lease_build')
# Canceling an existing build.
can_cancel_build = can_fn_for_build('cancel_build')
# Unleasing and resetting state of an existing build. Normally done by admins.
can_reset_build = can_fn_for_build('reset_build')
# Viewing ACLs.
can_read_acl = can_fn('read_acl')
# Changing ACLs.
can_write_acl = can_fn('write_acl')


def get_acl(bucket):
  """Returns ACL of |bucket|."""
  validate_bucket_name(bucket)
  if not can_read_acl(bucket):
    raise auth.AuthorizationError()
  return BucketAcl.get_by_id(bucket)


def set_acl(bucket, acl):
  """Overwrites ACL of |bucket|."""
  validate_bucket_name(bucket)
  assert isinstance(acl, BucketAcl)
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


################################################################################
## Implementation.


class Rule(ndb.Model):
  """A tuple of role and group.

  Stored inside BucketAcl.
  """
  role = ndb.StringProperty(required=True)
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
      validate_role_name(rule.role)
      validate_group_name(rule.group)


def has_any_of_roles(bucket, role_names, identity=None):
  """True if |identity| has any of given roles in |bucket|."""
  validate_bucket_name(bucket)
  for r in role_names:
    validate_role_name(r)
  identity = identity or auth.get_current_identity()

  if auth.is_admin(identity):
    return True

  role_names = set(role_names)
  bucket_acl = BucketAcl.get_by_id(bucket)
  if bucket_acl:
    for rule in bucket_acl.rules:
      if rule.role in role_names and auth.is_group_member(rule.group, identity):
        return True
  return False


def can(bucket, action, identity=None):
  validate_bucket_name(bucket)
  validate_action_name(action)
  return has_any_of_roles(bucket, ROLES_FOR_ACTION[action], identity)
