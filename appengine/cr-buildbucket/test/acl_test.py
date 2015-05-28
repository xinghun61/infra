# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from components import auth
from components import utils
from testing_utils import testing
import mock

from proto import project_config_pb2
import acl
import config
import errors
import model

# Shortcuts
Bucket = project_config_pb2.Bucket
Acl = project_config_pb2.Acl


class AclTest(testing.AppengineTestCase):
  def setUp(self):
    super(AclTest, self).setUp()
    self.current_identity = auth.Identity.from_bytes('user:a@example.com')
    self.mock(auth, 'get_current_identity', lambda: self.current_identity)
    self.mock(auth, 'is_admin', lambda: False)

    self.mock(config, 'get_buckets', mock.Mock())
    bucket_a = Bucket(
      name='a',
      acls=[
          Acl(role=Acl.WRITER, group='a-writers'),
          Acl(role=Acl.READER, group='a-readers'),
      ])
    bucket_b = Bucket(
      name='b',
      acls=[
          Acl(role=Acl.WRITER, group='b-writers'),
          Acl(role=Acl.READER, group='b-readers'),
      ])
    config.get_buckets.return_value = [bucket_a, bucket_b]

    def get_bucket(bucket):  # pragma: no cover
      if bucket == 'a':
        return bucket_a
      elif bucket == 'b':
        return bucket_b
      return None
    self.mock(config, 'get_bucket', get_bucket)

  def mock_is_group_member(self, groups):
    # pylint: disable=unused-argument
    def is_group_member(group, identity=None):
      return group in groups
    self.mock(auth, 'is_group_member', is_group_member)

  def test_has_any_of_roles(self):
    self.mock_is_group_member(['a-readers'])

    self.assertTrue(acl.has_any_of_roles('a', [Acl.READER]))
    self.assertTrue(acl.has_any_of_roles('a', [Acl.READER, Acl.WRITER]))
    self.assertFalse(acl.has_any_of_roles('a', [Acl.WRITER]))
    self.assertFalse(acl.has_any_of_roles('a', [Acl.WRITER, Acl.SCHEDULER]))
    self.assertFalse(acl.has_any_of_roles('b', [Acl.READER]))
    self.assertFalse(acl.has_any_of_roles('non.existing', [Acl.READER]))

    self.mock_is_group_member([])
    self.assertFalse(acl.has_any_of_roles('a', Acl.Role.values()))

    self.mock(auth, 'is_admin', lambda *_: True)
    self.assertTrue(acl.has_any_of_roles('a', [Acl.WRITER]))

  def test_get_available_buckets(self):
    self.mock_is_group_member(['xxx', 'yyy'])

    config.get_buckets.return_value = [
      Bucket(
          name='available_bucket1',
          acls=[
              Acl(role=Acl.READER, group='xxx'),
              Acl(role=Acl.WRITER, group='yyy')
          ],
      ),
      Bucket(
          name='available_bucket2',
          acls=[
              Acl(role=Acl.READER, group='xxx'),
              Acl(role=Acl.WRITER, group='zzz')
          ],
      ),
      Bucket(
          name='not_available_bucket',
          acls=[
            Acl(role=Acl.WRITER, group='zzz')],
      ),
    ]

    availble_buckets = acl.get_available_buckets()
    availble_buckets = acl.get_available_buckets()  # memcache coverage.
    self.assertEqual(
        availble_buckets, {'available_bucket1', 'available_bucket2'})

    self.mock(auth, 'is_admin', lambda *_: True)
    self.assertIsNone(acl.get_available_buckets())

  def mock_has_any_of_roles(self, current_identity_roles):
    current_identity_roles = set(current_identity_roles)
    def has_any_of_roles(_bucket, roles):
      return current_identity_roles.intersection(roles)
    self.mock(acl, 'has_any_of_roles', has_any_of_roles)

  def test_can(self):
    self.mock_has_any_of_roles([Acl.READER])
    self.assertTrue(acl.can('bucket', acl.Action.VIEW_BUILD))
    self.assertFalse(acl.can('bucket', acl.Action.CANCEL_BUILD))
    self.assertFalse(acl.can('bucket', acl.Action.WRITE_ACL))

    # Memcache coverage
    self.assertFalse(acl.can('bucket', acl.Action.WRITE_ACL))

  def test_can_no_roles(self):
    self.mock_has_any_of_roles([])
    for action in acl.Action:
      self.assertFalse(acl.can('bucket', action))

  def test_can_bad_input(self):
    with self.assertRaises(errors.InvalidInputError):
      acl.can('bad bucket name', acl.Action.VIEW_BUILD)

  def test_can_view_build(self):
    self.mock_has_any_of_roles([Acl.READER])
    build = model.Build(bucket='bucket')
    self.assertTrue(acl.can_view_build(build))
    self.assertFalse(acl.can_lease_build(build))
