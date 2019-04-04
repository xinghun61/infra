# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from components import auth
from testing_utils import testing
import mock

from google.appengine.ext import ndb

from proto import project_config_pb2
from test import test_util
from test.test_util import future
import config
import errors
import user

# Shortcuts
Bucket = project_config_pb2.Bucket
Acl = project_config_pb2.Acl


class UserTest(testing.AppengineTestCase):

  def setUp(self):
    super(UserTest, self).setUp()
    self.current_identity = auth.Identity.from_bytes('user:a@example.com')
    self.patch(
        'components.auth.get_current_identity',
        autospec=True,
        side_effect=lambda: self.current_identity
    )
    self.peer_identity = self.current_identity
    self.patch(
        'components.auth.get_peer_identity',
        autospec=True,
        side_effect=lambda: self.peer_identity
    )
    user.clear_request_cache()

    self.patch('components.auth.is_admin', autospec=True, return_value=False)

    bucket_a = Bucket(
        name='a',
        acls=[
            Acl(role=Acl.WRITER, group='a-writers'),
            Acl(role=Acl.READER, group='a-readers'),
        ]
    )
    bucket_b = Bucket(
        name='b',
        acls=[
            Acl(role=Acl.WRITER, group='b-writers'),
            Acl(role=Acl.READER, group='b-readers'),
        ]
    )
    bucket_c = Bucket(
        name='c',
        acls=[
            Acl(role=Acl.READER, group='c-readers'),
            Acl(role=Acl.READER, identity='user:a@example.com'),
            Acl(role=Acl.WRITER, group='c-writers'),
            Acl(role=Acl.READER, identity='project:p1'),
        ]
    )
    all_buckets = [('p1', bucket_a), ('p2', bucket_b), ('p3', bucket_c)]
    self.patch(
        'config.get_buckets_async',
        autospec=True,
        return_value=future(all_buckets)
    )

    bucket_map = {
        config.format_bucket_id(pid, b.name): b for pid, b in all_buckets
    }
    self.patch(
        'config.get_bucket_async',
        autospec=True,
        side_effect=lambda bid: future(('deadbeef', bucket_map.get(bid)))
    )

  def get_role(self, bucket_id):
    return user.get_role_async(bucket_id).get_result()

  @mock.patch('components.auth.is_group_member', autospec=True)
  def test_get_role(self, is_group_member):
    is_group_member.side_effect = lambda g, _=None: g == 'a-writers'

    self.assertEqual(self.get_role('p1/a'), Acl.WRITER)
    self.assertEqual(self.get_role('p2/a'), None)
    self.assertEqual(self.get_role('p3/c'), Acl.READER)
    self.assertEqual(self.get_role('p1/non.existing'), None)

    # Memcache test.
    user.clear_request_cache()
    self.assertEqual(self.get_role('p1/a'), Acl.WRITER)

  def test_get_role_admin(self):
    auth.is_admin.return_value = True
    self.assertEqual(self.get_role('p1/a'), Acl.WRITER)
    self.assertEqual(self.get_role('p1/non.existing'), None)

  @mock.patch('components.auth.is_group_member', autospec=True)
  def test_get_role_for_project(self, is_group_member):
    is_group_member.side_effect = lambda g, _=None: False

    self.current_identity = auth.Identity.from_bytes('project:p1')
    self.assertEqual(self.get_role('p1/a'), Acl.WRITER)  # implicit
    self.assertEqual(self.get_role('p2/b'), None)  # no roles at all
    self.assertEqual(self.get_role('p3/c'), Acl.READER)  # via explicit ACL

  @mock.patch('components.auth.is_group_member', autospec=True)
  def test_get_accessible_buckets_async(self, is_group_member):
    is_group_member.side_effect = lambda g, _=None: g in ('xxx', 'yyy')

    config.get_buckets_async.return_value = future({
        'p1/available_bucket1':
            Bucket(
                name='available_bucket1',
                acls=[
                    Acl(role=Acl.READER, group='xxx'),
                    Acl(role=Acl.WRITER, group='yyy')
                ],
            ),
        'p2/available_bucket2':
            Bucket(
                name='available_bucket2',
                acls=[
                    Acl(role=Acl.READER, group='xxx'),
                    Acl(role=Acl.WRITER, group='zzz')
                ],
            ),
        'p3/available_bucket3':
            Bucket(
                name='available_bucket3',
                acls=[
                    Acl(role=Acl.READER, identity='user:a@example.com'),
                ],
            ),
        'p4/not_available_bucket':
            Bucket(
                name='not_available_bucket',
                acls=[Acl(role=Acl.WRITER, group='zzz')],
            ),
    })

    # call twice for per-request caching of futures.
    user.get_accessible_buckets_async()
    availble_buckets = user.get_accessible_buckets_async().get_result()
    expected = {
        'p1/available_bucket1',
        'p2/available_bucket2',
        'p3/available_bucket3',
    }
    self.assertEqual(availble_buckets, expected)

    # call again for memcache coverage.
    user.clear_request_cache()
    availble_buckets = user.get_accessible_buckets_async().get_result()
    self.assertEqual(availble_buckets, expected)

  @mock.patch('components.auth.is_admin', autospec=True)
  def test_get_accessible_buckets_async_admin(self, is_admin):
    is_admin.return_value = True

    config.get_buckets_async.return_value = future([
        (
            'p1',
            Bucket(
                name='available_bucket1',
                acls=[
                    Acl(role=Acl.READER, group='xxx'),
                    Acl(role=Acl.WRITER, group='yyy')
                ],
            )
        ),
    ])

    self.assertIsNone(user.get_accessible_buckets_async().get_result())

  def mock_role(self, role):
    self.patch('user.get_role_async', return_value=future(role))

  def can(self, action):
    return user.can_async('project/bucket', action).get_result()

  def test_can(self):
    self.mock_role(Acl.READER)

    self.assertTrue(self.can(user.Action.VIEW_BUILD))
    self.assertFalse(self.can(user.Action.CANCEL_BUILD))
    self.assertFalse(self.can(user.Action.SET_NEXT_NUMBER))

    # Memcache coverage
    self.assertFalse(self.can(user.Action.SET_NEXT_NUMBER))

    self.assertFalse(user.can_add_build_async('project/bucket').get_result())

  def test_can_project_fallback(self):
    self.current_identity = auth.Identity.from_bytes('project:proj')

    good_peer = auth.Identity.from_bytes('user:good@example.com')
    bad_peer = auth.Identity.from_bytes('user:bad@example.com')

    def get_role(_, ident):
      return future(Acl.READER if ident == good_peer else None)

    self.patch(
        'user.get_role_async',
        autospec=True,
        side_effect=get_role,
    )

    self.peer_identity = good_peer
    self.assertTrue(self.can(user.Action.VIEW_BUILD))
    self.peer_identity = bad_peer
    self.assertFalse(self.can(user.Action.VIEW_BUILD))

  def test_can_no_roles(self):
    self.mock_role(None)
    bid = 'project/bucket'
    for action in user.Action:
      self.assertFalse(user.can_async(bid, action).get_result())

  def test_can_bad_input(self):
    with self.assertRaises(errors.InvalidInputError):
      bid = 'bad project id/bucket'
      user.can_async(bid, user.Action.VIEW_BUILD).get_result()
    with self.assertRaises(errors.InvalidInputError):
      bid = 'project_id/bad bucket name'
      user.can_async(bid, user.Action.VIEW_BUILD).get_result()

  def test_can_view_build(self):
    self.mock_role(Acl.READER)
    build = test_util.build()
    self.assertTrue(user.can_view_build_async(build).get_result())
    self.assertFalse(user.can_lease_build_async(build).get_result())

  @mock.patch('user.auth.delegate_async', autospec=True)
  def test_delegate_async(self, delegate_async):
    delegate_async.return_value = future('token')
    token = user.delegate_async(
        'swarming.example.com', tag='buildbucket:bucket:x'
    ).get_result()
    self.assertEqual(token, 'token')
    delegate_async.assert_called_with(
        audience=[user.self_identity()],
        services=['https://swarming.example.com'],
        impersonate=auth.get_current_identity(),
        tags=['buildbucket:bucket:x'],
    )

  def test_parse_identity(self):
    self.assertEqual(
        user.parse_identity('user:a@example.com'),
        auth.Identity('user', 'a@example.com'),
    )
    self.assertEqual(
        auth.Identity('user', 'a@example.com'),
        auth.Identity('user', 'a@example.com'),
    )

    self.assertEqual(
        user.parse_identity('a@example.com'),
        auth.Identity('user', 'a@example.com'),
    )

    with self.assertRaises(errors.InvalidInputError):
      user.parse_identity('a:b')


class GetOrCreateCachedFutureTest(testing.AppengineTestCase):
  maxDiff = None

  def test_unfinished_future_in_different_context(self):
    # This test essentially asserts ndb behavior that we assume in
    # user._get_or_create_cached_future.

    ident1 = auth.Identity.from_bytes('user:1@example.com')
    ident2 = auth.Identity.from_bytes('user:2@example.com')

    # First define a correct async function that uses caching.
    log = []

    @ndb.tasklet
    def compute_async(x):
      log.append('compute_async(%r) started' % x)
      yield ndb.sleep(0.001)
      log.append('compute_async(%r) finishing' % x)
      raise ndb.Return(x)

    def compute_cached_async(x):
      log.append('compute_cached_async(%r)' % x)
      # Use different identities to make sure _get_or_create_cached_future is
      # OK with that.
      ident = ident1 if x % 2 else ident2
      return user._get_or_create_cached_future(
          ident, x, lambda: compute_async(x)
      )

    # Now call compute_cached_async a few times, but stop on the first result,
    # and exit the current ndb context leaving remaining futures unfinished.

    class Error(Exception):
      pass

    with self.assertRaises(Error):
      # This code is intentionally looks realistic.
      futures = [compute_cached_async(x) for x in xrange(5)]
      for f in futures:  # pragma: no branch
        f.get_result()
        log.append('got result')
        # Something bad happened during processing.
        raise Error()

    # Assert that only first compute_async finished.
    self.assertEqual(
        log,
        [
            'compute_cached_async(0)',
            'compute_cached_async(1)',
            'compute_cached_async(2)',
            'compute_cached_async(3)',
            'compute_cached_async(4)',
            'compute_async(0) started',
            'compute_async(1) started',
            'compute_async(2) started',
            'compute_async(3) started',
            'compute_async(4) started',
            'compute_async(0) finishing',
            'got result',
        ],
    )
    log[:] = []

    # Now we assert that waiting for another future, continues execution.
    self.assertEqual(compute_cached_async(3).get_result(), 3)
    self.assertEqual(
        log,
        [
            'compute_cached_async(3)',
            'compute_async(1) finishing',
            'compute_async(2) finishing',
            'compute_async(3) finishing',
        ],
    )
    # Note that compute_async(4) didin't finish.
