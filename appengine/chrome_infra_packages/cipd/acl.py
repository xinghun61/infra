# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Access control list implementation."""

import collections

from google.appengine.ext import ndb
from components import auth

from . import impl


################################################################################
## Role inheritance.


# Predefined roles.
ROLES = [
  'OWNER',
  'WRITER',
  'READER',
]


def is_valid_role(role_name):
  """True if given string can be used as a role name."""
  return role_name in ROLES


def is_owner(package_path, identity):
  """True if |identity| has OWNER role for package subpath."""
  return has_role(package_path, 'OWNER', identity)


def is_writer(package_path, identity):
  """True if |identity| has WRITER role or better for package subpath."""
  return (
      has_role(package_path, 'WRITER', identity) or
      is_owner(package_path, identity))


def is_reader(package_path, identity):
  """True if |identity| has READER role or better for package subpath."""
  return (
      has_role(package_path, 'READER', identity) or
      is_writer(package_path, identity))


################################################################################
## Granular actions and mapping to roles. API uses these.

# Getting information about a package.
can_fetch_package = is_reader
# Creating a new package.
can_register_package = is_owner
# Fetching a package instance.
can_fetch_instance = is_reader
# Uploading a new instance to existing package.
can_register_instance = is_writer
# Creating or moving a ref. TODO(vadimsh): Make it per-ref.
can_move_ref = lambda package_path, ref, ident: is_writer(package_path, ident)
# Adding tags. TODO(vadimsh): Make it per-tag.
can_attach_tag = lambda package_path, tag, ident: is_writer(package_path, ident)
# Removing tags. TODO(vadimsh): Make it per-tag.
can_detach_tag = lambda package_path, tag, ident: is_writer(package_path, ident)
# Viewing ACLs.
can_fetch_acl = is_owner
# Changing ACLs.
can_modify_acl = is_owner


################################################################################
## Model.


# Describes single role modification. Passed to modify_roles.
RoleChange = collections.namedtuple('RoleChange', [
  # Package subpath to modify.
  'package_path',
  # True to remove the role, False to add it.
  'revoke',
  # Role to add\remove.
  'role',
  # Identity to add\remove role for. Only one of 'user' or 'group' can be set.
  'user',
  # Group to add\remove role for. Only one of 'user' or 'group' can be set.
  'group',
])


class PackageACLBody(ndb.Model):
  """Shared by PackageACL and PackageACLRevision.

  Doesn't actually exist in the datastore by itself. Only inherited from.
  """
  # Users granted the given role directly. Often only one account should be
  # granted some role (e.g. a role account should be WRITER). It is annoying to
  # manage one-account groups for cases like this.
  users = auth.IdentityProperty(indexed=False, repeated=True)
  # Groups granted the given role.
  groups = ndb.StringProperty(indexed=False, repeated=True)

  # Who made the last change.
  modified_by = auth.IdentityProperty(indexed=True)
  # When the last change was made.
  modified_ts = ndb.DateTimeProperty(indexed=True)


class PackageACL(PackageACLBody):
  """List of users and groups that have some role in some package.

  For role "R" and package "dir1/dir2" the entity key path is:
    [PackageACLRoot, (PackageACL, "R:dir1/dir2")].

  Notably:
    * There's a single root entity. All ACL entities belong to a single entity
      group. It allows transactional changes across different ACLs, but limits
      ACL changes to 1 change per second (which is more than enough, ACLs should
      not change very often).
    * ACLs for each roles are stored in separate entities (it allows to easily
      add new roles).
  """
  # Incremented with each change.
  rev = ndb.IntegerProperty(indexed=False, default=0)

  @property
  def package_path(self):
    chunks = self.key.id().split(':')
    assert len(chunks) == 2
    assert impl.is_valid_package_path(chunks[1])
    return chunks[1]

  @property
  def role(self):
    chunks = self.key.id().split(':')
    assert len(chunks) == 2
    assert is_valid_role(chunks[0])
    return chunks[0]

  def _pre_put_hook(self):
    chunks = self.key.id().split(':')
    assert len(chunks) == 2
    assert is_valid_role(chunks[0])
    assert impl.is_valid_package_path(chunks[1])


class PackageACLRevision(PackageACLBody):
  """Used to store historical values of some PackageACL.

  For role "R" and package "dir1/dir2" the entity key path is:
    [PackageACLRoot, (PackageACL, "R:dir1/dir2"), (PackageACLRevision, rev)].
  """


def root_key():
  """Returns ndb.Key of ACL model root entity."""
  return ndb.Key('PackageACLRoot', 'acls')


def package_acl_key(package_path, role):
  """Returns ndb.Key of some PackageACL entity."""
  assert impl.is_valid_package_path(package_path), package_path
  assert is_valid_role(role), role
  return ndb.Key(PackageACL, '%s:%s' % (role, package_path), parent=root_key())


def get_package_acls(package_path, role):
  """Returns a list of PackageACL entities with ACLs for given package path."""
  assert impl.is_valid_package_path(package_path), package_path
  assert is_valid_role(role), role
  components = package_path.split('/')
  keys = [
    package_acl_key('/'.join(components[:i+1]), role)
    for i in xrange(len(components))
  ]
  return filter(None, ndb.get_multi(keys))


def has_role(package_path, role, identity):
  """True if |identity| has |role| in some |package_path|."""
  assert impl.is_valid_package_path(package_path), package_path
  assert is_valid_role(role), role
  if auth.is_admin(identity):
    return True
  for acl in get_package_acls(package_path, role):
    if identity in acl.users:
      return True
    for group in acl.groups:
      if auth.is_group_member(group, identity):
        return True
  return False


def modify_roles(changes, caller, now):
  """Transactionally modifies ACLs for a bunch of packages and roles.

  Args:
    changes: list of RoleChange objects describing what modifications to apply.
        Order matters, modifications are applied in the order provided.
    caller: Identity that made this change.
    now: datetime with current time.

  Raises:
    ValueError if changes list contains bad changes.
  """
  if not changes:
    return

  # Validate format of changes.
  for c in changes:
    if not isinstance(c, RoleChange):
      raise ValueError(
          'Expecting RoleChange, got %s instead' % type(c).__name__)
    if not impl.is_valid_package_path(c.package_path):
      raise ValueError('Invalid package_path: %s' % c.package_path)
    if not is_valid_role(c.role):
      raise ValueError('Invalid role: %s' % c.role)
    if not c.user and not c.group:
      raise ValueError('RoleChange.user or RoleChange.group should be set')
    if c.user and c.group:
      raise ValueError(
          'Only one of RoleChange.user or RoleChange.group should be set')
    if c.user and not isinstance(c.user, auth.Identity):
      raise ValueError('RoleChange.user must be auth.Identity')
    if c.group and not auth.is_valid_group_name(c.group):
      raise ValueError('Invalid RoleChange.group value')

  @ndb.transactional
  def run():
    # (package_path, role) pair -> list of RoleChanges to apply to it.
    to_apply = collections.defaultdict(list)
    for c in changes:
      to_apply[(c.package_path, c.role)].append(c)

    # Grab all existing PackageACL entities, make new empty ones if missing.
    # Build mapping (package_path, role) -> PackageACL.
    entities = {}
    path_role_pairs = sorted(to_apply.keys())
    keys = [package_acl_key(path, role) for path, role in path_role_pairs]
    for i, entity in enumerate(ndb.get_multi(keys)):
      entities[path_role_pairs[i]] = entity or PackageACL(key=keys[i])

    # Helper to apply RoleChange to a list of users and groups.
    def apply_change(c, users, groups):
      if c.user:
        assert not c.group
        if c.revoke and c.user in users:
          users.remove(c.user)
        elif not c.revoke and c.user not in users:
          users.append(c.user)
      if c.group:
        assert not c.user
        if c.revoke and c.group in groups:
          groups.remove(c.group)
        elif not c.revoke and c.group not in groups:
          groups.append(c.group)

    # Apply all the changes. Collect a list of modified entities.
    to_put = []
    for package_path, role in path_role_pairs:
      package_acl = entities[(package_path, role)]
      change_list = to_apply[(package_path, role)]

      # Mutate lists of users and groups.
      users = list(package_acl.users)
      groups = list(package_acl.groups)
      for c in change_list:
        apply_change(c, users, groups)

      # Nothing changed?
      if users == package_acl.users and groups == package_acl.groups:
        continue

      # Store the previous revision in the log.
      if package_acl.rev:
        to_put.append(
            PackageACLRevision(
              key=ndb.Key(
                  PackageACLRevision, package_acl.rev, parent=package_acl.key),
              users=package_acl.users,
              groups=package_acl.groups,
              modified_by=package_acl.modified_by,
              modified_ts=package_acl.modified_ts))

      # Store modified PackageACL, bump revision.
      package_acl.users = users
      package_acl.groups = groups
      package_acl.modified_by = caller
      package_acl.modified_ts = now
      package_acl.rev += 1
      to_put.append(package_acl)

    # Apply all pending changes.
    ndb.put_multi(to_put)

  run()
