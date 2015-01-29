# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from components import auth
from components import utils
from testing_utils import testing
import mock

import acl
import errors
import model


class AclTest(testing.AppengineTestCase):
  def setUp(self):
    super(AclTest, self).setUp()
    self.current_identity = auth.Identity.from_bytes('user:a@example.com')
    self.mock(auth, 'get_current_identity', lambda: self.current_identity)

  def mock_admin(self):
    self.mock(auth, 'is_admin', lambda *_: True)

  def mock_is_group_member(self, groups):
    def is_group_member(group, identity):
      return identity == self.current_identity and group in groups
    self.mock(auth, 'is_group_member', is_group_member)

  def test_has_any_of_roles(self):
    self.mock_is_group_member(['readers'])

    acl.BucketAcl(
        id='bucket',
        rules=[
            acl.Rule(role='READER', group='readers'),
            acl.Rule(role='WRITER', group='writers'),
        ],
        modified_by=self.current_identity,
        modified_time=utils.utcnow(),
    ).put()

    self.assertTrue(acl.has_any_of_roles('bucket', ['READER']))
    self.assertTrue(acl.has_any_of_roles('bucket', ['READER', 'WRITER']))
    self.assertFalse(acl.has_any_of_roles('bucket', ['WRITER']))
    self.assertFalse(acl.has_any_of_roles('bucket', ['WRITER', 'OWNER']))
    self.assertFalse(acl.has_any_of_roles('another-bucket', ['READER']))

    self.mock_is_group_member([])
    self.assertFalse(acl.has_any_of_roles('bucket', acl.ROLES))

  def mock_has_any_of_roles(self, current_identity_roles):
    current_identity_roles = set(current_identity_roles)
    def has_any_of_roles(_bucket, roles, _identity):
      return current_identity_roles.intersection(roles)
    self.mock(acl, 'has_any_of_roles', has_any_of_roles)

  def test_can(self):
    self.mock_has_any_of_roles(['READER'])
    self.assertTrue(acl.can('bucket', 'view_build'))
    self.assertFalse(acl.can('bucket', 'cancel_build'))
    self.assertFalse(acl.can('bucket', 'write_acl'))

    self.mock_has_any_of_roles([])
    for action in acl.ALL_ACTIONS:
      self.assertFalse(acl.can('bucket', action))

    with self.assertRaises(errors.InvalidInputError):
      acl.can('bucket', 'invalid action')
    with self.assertRaises(errors.InvalidInputError):
      acl.can('bad bucket name', 'view_build')

  def test_can_view_build(self):
    self.mock_has_any_of_roles(['READER'])
    build = model.Build(bucket='bucket')
    self.assertTrue(acl.can_view_build(build))
    self.assertFalse(acl.can_lease_build(build))

  def test_writer_cannot_write_acl(self):
    self.mock_has_any_of_roles(['WRITER'])
    self.assertFalse(acl.can_read_acl('bucket'))
    self.assertFalse(acl.can_write_acl('bucket'))

  def test_get_acl(self):
    self.mock_admin()
    expected = acl.BucketAcl(
        id='bucket',
        rules=[acl.Rule(role='READER', group='readers')],
        modified_by=self.current_identity,
        modified_time=utils.utcnow(),
    )
    expected.put()

    actual = acl.get_acl('bucket')
    self.assertEqual(expected, actual)

    self.assertIsNone(acl.get_acl('unknown-bucket'))

  def test_get_acl_without_permissions(self):
    with self.assertRaises(auth.AuthorizationError):
      acl.get_acl('bucket')

  def test_set_acl(self):
    now = datetime.datetime(2015, 1, 1)
    self.mock(utils, 'utcnow', lambda: now)

    self.mock_admin()
    expected = acl.BucketAcl(
        rules=[acl.Rule(
            role='READER',
            group='readers',
        )]
    )

    acl.set_acl('bucket', expected)

    actual = acl.BucketAcl.get_by_id('bucket')
    self.assertEqual(actual, expected)
    self.assertEqual(actual.modified_by, self.current_identity)
    self.assertEqual(actual.modified_time, utils.utcnow())

  def test_set_acl_without_permissions(self):
    acls = acl.BucketAcl(
        rules=[acl.Rule(
            role='READER',
            group='readers',
        )]
    )

    with self.assertRaises(auth.AuthorizationError):
      acl.set_acl('bucket', acls)

  def test_set_acl_with_bad_input(self):
    self.mock_admin()
    with self.assertRaises(errors.InvalidInputError):
      acl.set_acl('bad bucket name', acl.BucketAcl())

    with self.assertRaises(errors.InvalidInputError):
      acl.set_acl(
          'good-bucket-name',
          acl.BucketAcl(rules=[
              acl.Rule(role='bad role name', group='good-group-name')
          ]))

    with self.assertRaises(errors.InvalidInputError):
      acl.set_acl(
          'good-bucket-name',
          acl.BucketAcl(rules=[
              acl.Rule(role='READER', group='bad:group name')
          ]))
