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

  def set_acl(self, bucket_name, rules):
    bucket_acl = acl.BucketAcl(
        id=bucket_name,
        rules=rules,
        modified_by=self.current_identity,
        modified_time=utils.utcnow(),
    )
    bucket_acl.put()
    return bucket_acl

  def mock_admin(self):
    self.mock(auth, 'is_admin', lambda *_: True)

  def mock_is_group_member(self, groups):
    def is_group_member(group, identity):
      return identity == self.current_identity and group in groups
    self.mock(auth, 'is_group_member', is_group_member)

  def test_has_any_of_roles(self):
    self.mock_is_group_member(['readers'])

    self.set_acl(
        'bucket',
        [
            acl.Rule(role=acl.Role.READER, group='readers'),
            acl.Rule(role=acl.Role.WRITER, group='writers'),
        ])

    self.assertTrue(
        acl.has_any_of_roles('bucket', [acl.Role.READER]))
    self.assertTrue(
        acl.has_any_of_roles('bucket', [acl.Role.READER, acl.Role.WRITER]))
    self.assertFalse(
        acl.has_any_of_roles('bucket', [acl.Role.WRITER]))
    self.assertFalse(
        acl.has_any_of_roles('bucket', [acl.Role.WRITER, acl.Role.OWNER]))
    self.assertFalse(
        acl.has_any_of_roles('another-bucket', [acl.Role.READER]))

    self.mock_is_group_member([])
    self.assertFalse(acl.has_any_of_roles('bucket', acl.Role))

  def test_get_available_buckets(self):
    self.mock_is_group_member(['xxx', 'yyy'])


    self.set_acl(
        'available_bucket1',
        [
            acl.Rule(role=acl.Role.READER, group='xxx'),
            acl.Rule(role=acl.Role.WRITER, group='yyy')
        ],
    )
    self.set_acl(
        'available_bucket2',
        [
            acl.Rule(role=acl.Role.READER, group='xxx'),
            acl.Rule(role=acl.Role.WRITER, group='zzz')
        ],
    )
    self.set_acl(
        'not_available_bucket',
        [acl.Rule(role=acl.Role.OWNER, group='zzz')],
    )

    availble_buckets = acl.get_available_buckets()
    availble_buckets = acl.get_available_buckets()  # memcache coverage.
    self.assertEqual(
        availble_buckets, {'available_bucket1', 'available_bucket2'})

    self.mock(auth, 'is_admin', lambda _: True)
    self.assertIsNone(acl.get_available_buckets())

  def mock_has_any_of_roles(self, current_identity_roles):
    current_identity_roles = set(current_identity_roles)
    def has_any_of_roles(_bucket, roles, _identity):
      return current_identity_roles.intersection(roles)
    self.mock(acl, 'has_any_of_roles', has_any_of_roles)

  def test_can(self):
    self.mock_has_any_of_roles([acl.Role.READER])
    self.assertTrue(acl.can('bucket', acl.Action.VIEW_BUILD))
    self.assertFalse(acl.can('bucket', acl.Action.CANCEL_BUILD))
    self.assertFalse(acl.can('bucket', acl.Action.WRITE_ACL))

    self.mock_has_any_of_roles([])
    for action in acl.Action:
      self.assertFalse(acl.can('bucket', action))

    with self.assertRaises(errors.InvalidInputError):
      acl.can('bad bucket name', acl.Action.VIEW_BUILD)

  def test_can_view_build(self):
    self.mock_has_any_of_roles([acl.Role.READER])
    build = model.Build(bucket='bucket')
    self.assertTrue(acl.can_view_build(build))
    self.assertFalse(acl.can_lease_build(build))

  def test_writer_cannot_write_acl(self):
    self.mock_has_any_of_roles([acl.Role.WRITER])
    self.assertFalse(acl.can_read_acl('bucket'))
    self.assertFalse(acl.can_write_acl('bucket'))

  def test_get_acl(self):
    self.mock_admin()
    expected = self.set_acl(
        'bucket', [acl.Rule(role=acl.Role.READER, group='readers')])

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
        rules=[
            acl.Rule(
                role=acl.Role.READER,
                group='readers',
            ),
        ],
    )

    acl.set_acl('bucket', expected)

    actual = acl.BucketAcl.get_by_id('bucket')
    self.assertEqual(actual, expected)
    self.assertEqual(actual.modified_by, self.current_identity)
    self.assertEqual(actual.modified_time, utils.utcnow())

  def test_set_acl_without_permissions(self):
    acls = acl.BucketAcl(
        rules=[acl.Rule(
            role=acl.Role.READER,
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
              acl.Rule(role=acl.Role.READER, group='bad:group name'),
          ],
      ))
