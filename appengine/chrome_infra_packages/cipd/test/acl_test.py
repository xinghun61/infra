# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from google.appengine.ext import ndb
from testing_utils import testing

from components import auth
from components import auth_testing

from cipd import acl


class TestRepoServiceACL(testing.AppengineTestCase):
  def test_is_owner_writer_reader(self):
    mocked_roles = []
    caller = auth.Identity.from_bytes('user:abc@example.com')
    def mocked_has_role(package_path, role, ident):
      self.assertEqual('a/b', package_path)
      self.assertEqual(caller, ident)
      return role in mocked_roles
    self.mock(acl, 'has_role', mocked_has_role)

    mocked_roles = ['OWNER']
    self.assertTrue(acl.is_owner('a/b', caller))
    self.assertTrue(acl.is_writer('a/b', caller))
    self.assertTrue(acl.is_reader('a/b', caller))
    self.assertTrue(acl.can_attach_tag('a/b', 'tag1:', caller))
    self.assertTrue(acl.can_detach_tag('a/b', 'tag1:', caller))

    mocked_roles = ['WRITER']
    self.assertFalse(acl.is_owner('a/b', caller))
    self.assertTrue(acl.is_writer('a/b', caller))
    self.assertTrue(acl.is_reader('a/b', caller))
    self.assertTrue(acl.can_attach_tag('a/b', 'tag1:', caller))
    self.assertTrue(acl.can_detach_tag('a/b', 'tag1:', caller))

    mocked_roles = ['READER']
    self.assertFalse(acl.is_owner('a/b', caller))
    self.assertFalse(acl.is_writer('a/b', caller))
    self.assertTrue(acl.is_reader('a/b', caller))
    self.assertFalse(acl.can_attach_tag('a/b', 'tag1:', caller))
    self.assertFalse(acl.can_detach_tag('a/b', 'tag1:', caller))

    mocked_roles = []
    self.assertFalse(acl.is_owner('a/b', caller))
    self.assertFalse(acl.is_writer('a/b', caller))
    self.assertFalse(acl.is_reader('a/b', caller))
    self.assertFalse(acl.can_attach_tag('a/b', 'tag1:', caller))
    self.assertFalse(acl.can_detach_tag('a/b', 'tag1:', caller))

  def test_has_role_admin(self):
    auth_testing.mock_is_admin(self, False)
    self.assertFalse(
        acl.has_role('package', 'OWNER', auth_testing.DEFAULT_MOCKED_IDENTITY))
    auth_testing.mock_is_admin(self, True)
    self.assertTrue(
        acl.has_role('package', 'OWNER', auth_testing.DEFAULT_MOCKED_IDENTITY))

  def test_package_acl_key(self):
    self.assertEqual(
        ndb.Key('PackageACLRoot', 'acls', 'PackageACL', 'OWNER:a/b/c'),
        acl.package_acl_key('a/b/c', 'OWNER'))

  def test_has_role(self):
    acl.PackageACL(
        key=acl.package_acl_key('a', 'OWNER'),
        users=[auth.Identity.from_bytes('user:root-owner@example.com')]).put()
    acl.PackageACL(
        key=acl.package_acl_key('a/b/c', 'OWNER'),
        groups=['mid-group']).put()
    acl.PackageACL(
        key=acl.package_acl_key('a/b/c/d/e', 'OWNER'),
        groups=['leaf-group']).put()

    # Verify get_package_acls works.
    self.assertEqual(
        [('a', 'OWNER'), ('a/b/c', 'OWNER'), ('a/b/c/d/e', 'OWNER')],
        [
          (e.package_path, e.role)
          for e in acl.get_package_acls('a/b/c/d/e/f', 'OWNER')
        ])

    # Mock groups.
    def mocked_is_group_member(group, ident):
      if group == 'mid-group' and ident.name == 'mid-owner@example.com':
        return True
      if group == 'leaf-group' and ident.name == 'leaf-owner@example.com':
        return True
      return False
    self.mock(acl.auth, 'is_group_member', mocked_is_group_member)

    # Verify has_role works.
    check = lambda p, i: acl.has_role(p, 'OWNER', auth.Identity.from_bytes(i))
    self.assertTrue(check('a', 'user:root-owner@example.com'))
    self.assertFalse(check('b', 'user:root-owner@example.com'))
    self.assertTrue(check('a/b/c/d/e/f', 'user:root-owner@example.com'))
    self.assertFalse(check('a', 'user:mid-owner@example.com'))
    self.assertTrue(check('a/b/c/d/e/f', 'user:mid-owner@example.com'))
    self.assertFalse(check('a/b/c/d', 'user:leaf-owner@example.com'))
    self.assertTrue(check('a/b/c/d/e/f', 'user:leaf-owner@example.com'))

  def test_modify_roles_empty(self):
    # Just for code coverage.
    acl.modify_roles(
        changes=[],
        caller=auth.Identity.from_bytes('user:a@example.com'),
        now=datetime.datetime(2014, 1, 1))

  def test_modify_roles_validation(self):
    with self.assertRaises(ValueError):
      acl.modify_roles(
          changes=['not a RoleChange'],
          caller=auth.Identity.from_bytes('user:a@example.com'),
          now=datetime.datetime(2014, 1, 1))

    def should_fail(
        package_path='a', revoke=False, role='OWNER', user=None, group='group'):
      with self.assertRaises(ValueError):
        acl.modify_roles(
            changes=[
              acl.RoleChange(
                  package_path=package_path,
                  revoke=revoke,
                  role=role,
                  user=user,
                  group=group),
            ],
            caller=auth.Identity.from_bytes('user:a@example.com'),
            now=datetime.datetime(2014, 1, 1))

    should_fail(package_path='bad path')
    should_fail(role='BAD_ROLE')
    should_fail(user=None, group=None)
    should_fail(user=auth.Identity.from_bytes('user:a@abc.com'), group='group')
    should_fail(user='not Identity', group=None)
    should_fail(group='bad/group/name')

  def test_modify_roles(self):
    ident_a = auth.Identity.from_bytes('user:a@example.com')
    ident_b = auth.Identity.from_bytes('user:b@example.com')

    # Modify a bunch of packages. Include some redundant and self-canceling
    # changes to test all code paths.
    acl.modify_roles(
        changes=[
          acl.RoleChange(
            package_path='a',
            revoke=False,
            role='OWNER',
            user=ident_a,
            group=None),
          acl.RoleChange(
            package_path='a',
            revoke=False,
            role='OWNER',
            user=ident_a,
            group=None),
          acl.RoleChange(
            package_path='a',
            revoke=False,
            role='OWNER',
            user=ident_b,
            group=None),
          acl.RoleChange(
            package_path='a/b',
            revoke=False,
            role='OWNER',
            user=None,
            group='some-group'),
          acl.RoleChange(
            package_path='a/b',
            revoke=False,
            role='OWNER',
            user=None,
            group='some-group'),
          acl.RoleChange(
            package_path='a/b/c',
            revoke=False,
            role='OWNER',
            user=ident_a,
            group=None),
          acl.RoleChange(
            package_path='a/b/c',
            revoke=True,
            role='OWNER',
            user=ident_a,
            group=None),
        ],
        caller=ident_a,
        now=datetime.datetime(2014, 1, 1))

    # Ensure modification have been applied correctly.
    self.assertEqual({
      'groups': [],
      'modified_by': ident_a,
      'modified_ts': datetime.datetime(2014, 1, 1, 0, 0),
      'rev': 1,
      'users': [ident_a, ident_b],
    }, acl.package_acl_key('a', 'OWNER').get().to_dict())
    self.assertEqual({
      'groups': ['some-group'],
      'modified_by': ident_a,
      'modified_ts': datetime.datetime(2014, 1, 1, 0, 0),
      'rev': 1,
      'users': [],
    }, acl.package_acl_key('a/b', 'OWNER').get().to_dict())
    self.assertEqual(None, acl.package_acl_key('a/b/c', 'OWNER').get())

    # Modify same ACLs again.
    acl.modify_roles(
        changes=[
          acl.RoleChange(
            package_path='a',
            revoke=True,
            role='OWNER',
            user=ident_a,
            group=None),
          acl.RoleChange(
            package_path='a',
            revoke=False,
            role='OWNER',
            user=None,
            group='some-group'),
          acl.RoleChange(
            package_path='a/b',
            revoke=True,
            role='OWNER',
            user=None,
            group='some-group'),
        ],
        caller=ident_b,
        now=datetime.datetime(2015, 1, 1))

    # Ensure modification have been applied correctly.
    self.assertEqual({
      'groups': ['some-group'],
      'modified_by': ident_b,
      'modified_ts': datetime.datetime(2015, 1, 1, 0, 0),
      'rev': 2,
      'users': [ident_b],
    }, acl.package_acl_key('a', 'OWNER').get().to_dict())

    # Ensure previous version has been saved in the revision log.
    rev_key = ndb.Key(
        acl.PackageACLRevision, 1, parent=acl.package_acl_key('a', 'OWNER'))
    self.assertEqual({
      'groups': [],
      'modified_by': ident_a,
      'modified_ts': datetime.datetime(2014, 1, 1, 0, 0),
      'users': [ident_a, ident_b],
    }, rev_key.get().to_dict())
