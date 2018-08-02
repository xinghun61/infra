# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

from google.appengine.ext import ndb

from components import auth
from components import utils
from testing_utils import testing

from proto import common_pb2
from proto.config import project_config_pb2
from test.test_util import future
import errors
import model
import search
import user


class ValidateQueryTests(testing.AppengineTestCase):

  def test_invalid_status(self):
    q = search.Query(status=[],)
    err_pattern = r'status must be a StatusFilter, int or None'
    with self.assertRaisesRegexp(errors.InvalidInputError, err_pattern):
      q.validate()

  def test_two_ranges(self):
    q = search.Query(
        create_time_low=datetime.datetime(2018, 1, 1),
        build_high=1000,
    )
    err_pattern = r'mutually exclusive'
    with self.assertRaisesRegexp(errors.InvalidInputError, err_pattern):
      q.validate()


class SearchTest(testing.AppengineTestCase):
  INDEXED_TAG = 'buildset:1'

  def setUp(self):
    super(SearchTest, self).setUp()

    self.current_identity = auth.Identity('service', 'unittest')
    self.patch(
        'components.auth.get_current_identity',
        side_effect=lambda: self.current_identity
    )
    self.patch('user.can_async', return_value=future(True))
    self.patch(
        'user.get_acessible_buckets_async',
        autospec=True,
        return_value=future(['chromium']),
    )
    self.now = datetime.datetime(2015, 1, 1)
    self.patch('components.utils.utcnow', side_effect=lambda: self.now)

    self.chromium_bucket = project_config_pb2.Bucket(name='chromium')
    self.chromium_project_id = 'test'
    self.patch(
        'config.get_bucket_async',
        return_value=future(('project', self.chromium_bucket))
    )

    self.test_build = model.Build(
        id=model.create_build_ids(self.now, 1)[0],
        bucket='chromium',
        project=self.chromium_project_id,
        create_time=self.now,
        tags=[self.INDEXED_TAG],
        parameters={
            model.BUILDER_PARAMETER:
                'infra',
            'changes': [{
                'author': 'nodir@google.com',
                'message': 'buildbucket: initial commit'
            }],
        },
        canary=False,
    )
    self.patch('search.TagIndex.random_shard_index', return_value=0)

  def mock_cannot(self, action, bucket=None):

    def can_async(requested_bucket, requested_action, _identity=None):
      match = (
          requested_action == action and
          (bucket is None or requested_bucket == bucket)
      )
      return future(not match)

    # user.can_async is patched in setUp()
    user.can_async.side_effect = can_async

  def put_many_builds(self, count=100, tags=None):
    tags = tags or []
    builds = []
    for _ in xrange(count):
      b = model.Build(
          id=model.create_build_ids(self.now, 1)[0],
          bucket=self.test_build.bucket,
          tags=tags,
          create_time=self.now
      )
      self.now += datetime.timedelta(seconds=1)
      self.put_build(b)
      builds.append(b)
    return builds

  def put_build(self, build):
    """Puts a build and updates tag index."""
    build.put()

    index_entry = search.TagIndexEntry(
        bucket=build.bucket,
        build_id=build.key.id(),
    )
    for t in search.indexed_tags(build.tags):
      search.add_to_tag_index_async(t, [index_entry]).get_result()

  def search(self, **query_attrs):
    return search.search_async(search.Query(**query_attrs)).get_result()

  def assert_equal_keys(self, first, second):
    keys = lambda builds: [b.key for b in builds]
    self.assertEqual(keys(first), keys(second))

  def test_search(self):
    build2 = model.Build(bucket=self.test_build.bucket)
    self.put_build(build2)

    self.test_build.tags = ['important:true']
    self.put_build(self.test_build)
    builds, _ = self.search(
        buckets=[self.test_build.bucket],
        tags=self.test_build.tags,
    )
    self.assertEqual(builds, [self.test_build])

  def test_search_without_buckets(self):
    self.mock_cannot(user.Action.SEARCH_BUILDS, 'other bucket')

    build2 = model.Build(bucket='other bucket', tags=[self.INDEXED_TAG])
    self.put_build(self.test_build)
    self.put_build(build2)

    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [self.test_build])
    builds, _ = self.search()
    self.assertEqual(builds, [self.test_build])

    # All buckets are available.
    user.get_acessible_buckets_async.return_value = future(None)
    user.can_async.side_effect = None
    builds, _ = self.search()
    self.assertEqual(builds, [build2, self.test_build])
    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [build2, self.test_build])

    # No buckets are available.
    user.get_acessible_buckets_async.return_value = future([])
    self.mock_cannot(user.Action.SEARCH_BUILDS)
    builds, _ = self.search()
    self.assertEqual(builds, [])
    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [])

  def test_search_with_auth_error(self):
    self.mock_cannot(user.Action.SEARCH_BUILDS)
    self.put_build(self.test_build)

    with self.assertRaises(auth.AuthorizationError):
      self.search(buckets=[self.test_build.bucket])

  def test_search_many_tags(self):
    self.test_build.tags = [self.INDEXED_TAG, 'important:true', 'author:ivan']
    self.put_build(self.test_build)
    build2 = model.Build(
        bucket=self.test_build.bucket,
        tags=self.test_build.tags[:2],  # not authored by Ivan.
    )
    self.put_build(build2)

    # Search by both tags.
    builds, _ = self.search(
        tags=[self.INDEXED_TAG, 'important:true', 'author:ivan'],
        buckets=[self.test_build.bucket],
    )
    self.assertEqual(builds, [self.test_build])

    builds, _ = self.search(
        tags=['important:true', 'author:ivan'],
        buckets=[self.test_build.bucket],
    )
    self.assertEqual(builds, [self.test_build])

  def test_search_by_build_address(self):
    build_address = 'build_address:chromium/infra/1'
    self.test_build.tags = [build_address]
    self.put_build(self.test_build)

    user.get_acessible_buckets_async.return_value = future([
        self.test_build.bucket
    ])
    builds, _ = self.search(tags=[build_address])
    self.assertEqual(builds, [self.test_build])

  def test_search_bucket(self):
    self.put_build(self.test_build)
    build2 = model.Build(bucket='other bucket',)
    self.put_build(build2)

    builds, _ = self.search(buckets=[self.test_build.bucket])
    self.assertEqual(builds, [self.test_build])

  def test_search_by_status(self):
    self.put_build(self.test_build)
    build2 = model.Build(
        bucket=self.test_build.bucket,
        status=model.BuildStatus.COMPLETED,
        result=model.BuildResult.SUCCESS,
        create_time=utils.utcnow(),
        complete_time=utils.utcnow() + datetime.timedelta(seconds=1),
        canary=False,
    )
    self.put_build(build2)

    builds, _ = self.search(
        buckets=[self.test_build.bucket], status=search.StatusFilter.SCHEDULED
    )
    self.assertEqual(builds, [self.test_build])
    builds, _ = self.search(
        buckets=[self.test_build.bucket],
        status=search.StatusFilter.SCHEDULED,
        tags=[self.INDEXED_TAG]
    )
    self.assertEqual(builds, [self.test_build])

    builds, _ = self.search(
        buckets=[self.test_build.bucket],
        status=search.StatusFilter.COMPLETED,
        result=model.BuildResult.FAILURE,
        tags=[self.INDEXED_TAG]
    )
    self.assertEqual(builds, [])
    builds, _ = self.search(
        buckets=[self.test_build.bucket],
        status=search.StatusFilter.COMPLETED,
        result=model.BuildResult.FAILURE
    )
    self.assertEqual(builds, [])

    builds, _ = self.search(
        buckets=[self.test_build.bucket], status=search.StatusFilter.INCOMPLETE
    )
    self.assertEqual(builds, [self.test_build])
    builds, _ = self.search(
        buckets=[self.test_build.bucket],
        status=search.StatusFilter.INCOMPLETE,
        tags=[self.INDEXED_TAG]
    )
    self.assertEqual(builds, [self.test_build])

  def test_search_by_status_v2(self):
    self.put_build(self.test_build)
    build2 = model.Build(
        bucket=self.test_build.bucket,
        status=model.BuildStatus.COMPLETED,
        result=model.BuildResult.SUCCESS,
        create_time=utils.utcnow(),
        complete_time=utils.utcnow() + datetime.timedelta(seconds=1),
        canary=False,
    )
    self.put_build(build2)

    builds, _ = self.search(
        buckets=[self.test_build.bucket], status=common_pb2.SCHEDULED
    )
    self.assertEqual(builds, [self.test_build])
    builds, _ = self.search(
        buckets=[self.test_build.bucket],
        status=common_pb2.SCHEDULED,
        tags=[self.INDEXED_TAG]
    )
    self.assertEqual(builds, [self.test_build])

    builds, _ = self.search(
        buckets=[self.test_build.bucket],
        status=common_pb2.FAILURE,
        tags=[self.INDEXED_TAG]
    )
    self.assertEqual(builds, [])
    builds, _ = self.search(
        buckets=[self.test_build.bucket], status=common_pb2.FAILURE
    )
    self.assertEqual(builds, [])

  def test_search_by_created_by(self):
    self.put_build(self.test_build)
    build2 = model.Build(
        bucket=self.test_build.bucket,
        tags=[self.INDEXED_TAG],
        created_by=auth.Identity.from_bytes('user:x@chromium.org')
    )
    self.put_build(build2)

    builds, _ = self.search(
        created_by='x@chromium.org',
        buckets=[self.test_build.bucket],
    )
    self.assertEqual(builds, [build2])
    builds, _ = self.search(
        created_by='x@chromium.org',
        buckets=[self.test_build.bucket],
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [build2])

  def test_search_by_build_id_range_lo(self):
    builds = self.put_many_builds(count=5)
    # make builds order same as search results order
    builds.reverse()

    actual, _ = self.search(build_low=builds[0].key.id())
    self.assert_equal_keys(builds, actual)

    actual, _ = self.search(build_low=builds[0].key.id() + 1)
    self.assert_equal_keys(builds[1:], actual)

  def test_search_by_build_id_range_hi(self):
    builds = self.put_many_builds(count=5)
    # make builds order same as search results order
    builds.reverse()

    actual, _ = self.search(build_high=builds[-1].key.id())
    self.assert_equal_keys(builds[:-1], actual)

    actual, _ = self.search(build_high=builds[-1].key.id() + 1)
    self.assert_equal_keys(builds, actual)

  def test_search_by_creation_time_range(self):
    too_old = model.BEGINING_OF_THE_WORLD - datetime.timedelta(milliseconds=1)
    old_time = model.BEGINING_OF_THE_WORLD + datetime.timedelta(milliseconds=1)
    new_time = datetime.datetime(2012, 12, 5)

    create_time = datetime.datetime(2011, 2, 4)
    old_build = model.Build(
        id=model.create_build_ids(create_time, 1)[0],
        bucket=self.test_build.bucket,
        tags=[self.INDEXED_TAG],
        created_by=auth.Identity.from_bytes('user:x@chromium.org'),
        create_time=create_time,
    )
    self.put_build(old_build)
    self.put_build(self.test_build)

    # Test lower bound

    builds, _ = self.search(
        create_time_low=too_old,
        buckets=[self.test_build.bucket],
    )
    self.assertEqual(builds, [self.test_build, old_build])

    builds, _ = self.search(
        create_time_low=old_time,
        buckets=[self.test_build.bucket],
    )
    self.assertEqual(builds, [self.test_build, old_build])

    builds, _ = self.search(
        create_time_low=old_time,
        buckets=[self.test_build.bucket],
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [self.test_build, old_build])

    builds, _ = self.search(
        create_time_low=new_time,
        buckets=[self.test_build.bucket],
    )
    self.assertEqual(builds, [self.test_build])

    builds, _ = self.search(
        create_time_low=new_time,
        buckets=[self.test_build.bucket],
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [self.test_build])

    # Test upper bound

    builds, _ = self.search(
        create_time_high=too_old,
        buckets=[self.test_build.bucket],
    )
    self.assertEqual(builds, [])

    builds, _ = self.search(
        create_time_high=old_time,
        buckets=[self.test_build.bucket],
    )
    self.assertEqual(builds, [])

    builds, _ = self.search(
        create_time_high=old_time,
        buckets=[self.test_build.bucket],
        tags=[self.INDEXED_TAG],
    )
    builds, _ = self.search(
        create_time_high=new_time,
        buckets=[self.test_build.bucket],
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [old_build])

    builds, _ = self.search(
        create_time_high=(
            self.test_build.create_time + datetime.timedelta(milliseconds=1)
        ),
        buckets=[self.test_build.bucket],
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [self.test_build, old_build])

    # Test both sides bounded

    builds, _ = self.search(
        create_time_low=new_time,
        create_time_high=old_time,
        buckets=[self.test_build.bucket],
    )
    self.assertEqual(builds, [])

    builds, _ = self.search(
        create_time_low=old_time,
        create_time_high=new_time,
        buckets=[self.test_build.bucket],
    )
    self.assertEqual(builds, [old_build])

    builds, _ = self.search(
        create_time_low=old_time,
        create_time_high=new_time,
        buckets=[self.test_build.bucket],
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [old_build])

    # Test reversed bounds

    builds, _ = self.search(
        create_time_low=new_time,
        create_time_high=old_time,
        buckets=[self.test_build.bucket],
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [])

  def test_search_by_retry_of(self):
    self.put_build(self.test_build)
    build2 = model.Build(
        bucket=self.test_build.bucket,
        retry_of=42,
        tags=[self.INDEXED_TAG],
    )
    self.put_build(build2)

    builds, _ = self.search(retry_of=42)
    self.assertEqual(builds, [build2])
    builds, _ = self.search(retry_of=42, tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [build2])

  def test_search_by_retry_of_and_buckets(self):
    self.test_build.retry_of = 42
    self.put_build(self.test_build)
    self.put_build(model.Build(bucket='other bucket', retry_of=42))

    builds, _ = self.search(
        retry_of=42,
        buckets=[self.test_build.bucket],
    )
    self.assertEqual(builds, [self.test_build])
    builds, _ = self.search(
        retry_of=42,
        buckets=[self.test_build.bucket],
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [self.test_build])

  def test_search_by_retry_of_with_auth_error(self):
    self.mock_cannot(user.Action.SEARCH_BUILDS, bucket=self.test_build.bucket)
    self.put_build(self.test_build)
    build2 = model.Build(
        bucket=self.test_build.bucket,
        retry_of=self.test_build.key.id(),
    )
    self.put_build(build2)

    with self.assertRaises(auth.AuthorizationError):
      # The build we are looking for was a retry of a build that is in a bucket
      # that we don't have access to.
      self.search(retry_of=self.test_build.key.id())
    with self.assertRaises(auth.AuthorizationError):
      # The build we are looking for was a retry of a build that is in a bucket
      # that we don't have access to.
      self.search(retry_of=self.test_build.key.id(), tags=[self.INDEXED_TAG])

  def test_search_by_created_by_with_bad_string(self):
    with self.assertRaises(errors.InvalidInputError):
      self.search(created_by='blah')

  def test_search_with_paging_using_datastore_query(self):
    self.put_many_builds()

    first_page, next_cursor = self.search(
        buckets=[self.test_build.bucket],
        max_builds=10,
    )
    self.assertEqual(len(first_page), 10)
    self.assertTrue(next_cursor)

    second_page, _ = self.search(
        buckets=[self.test_build.bucket],
        max_builds=10,
        start_cursor=next_cursor
    )
    self.assertEqual(len(second_page), 10)
    # no cover due to a bug in coverage (http://stackoverflow.com/a/35325514)
    self.assertTrue(any(new not in first_page for new in second_page)
                   )  # pragma: no cover

  def test_search_with_paging_using_tag_index(self):
    self.put_many_builds(20, tags=[self.INDEXED_TAG])

    first_page, first_cursor = self.search(
        tags=[self.INDEXED_TAG],
        max_builds=10,
    )
    self.assertEqual(len(first_page), 10)
    self.assertEqual(first_cursor, 'id>%d' % first_page[-1].key.id())

    second_page, second_cursor = self.search(
        tags=[self.INDEXED_TAG], max_builds=10, start_cursor=first_cursor
    )
    self.assertEqual(len(second_page), 10)

    third_page, third_cursor = self.search(
        tags=[self.INDEXED_TAG], max_builds=10, start_cursor=second_cursor
    )
    self.assertEqual(len(third_page), 0)
    self.assertFalse(third_cursor)

  def test_search_with_bad_tags(self):

    def test_bad_tag(tags):
      with self.assertRaises(errors.InvalidInputError):
        self.search(buckets=['bucket'], tags=tags)

    test_bad_tag(['x'])
    test_bad_tag([1])
    test_bad_tag({})
    test_bad_tag(1)

  def test_search_with_bad_buckets(self):
    with self.assertRaises(errors.InvalidInputError):
      self.search(buckets={})
    with self.assertRaises(errors.InvalidInputError):
      self.search(buckets=[1])

  def test_search_with_non_number_max_builds(self):
    with self.assertRaises(errors.InvalidInputError):
      self.search(buckets=['b'], tags=['a:b'], max_builds='a')

  def test_search_with_negative_max_builds(self):
    with self.assertRaises(errors.InvalidInputError):
      self.search(buckets=['b'], tags=['a:b'], max_builds=-2)

  def test_search_by_indexed_tag(self):
    self.put_build(self.test_build)

    secret_build = model.Build(
        bucket='secret.bucket',
        tags=[self.INDEXED_TAG],
    )
    self.put_build(secret_build)

    different_buildset = model.Build(
        bucket='secret.bucket',
        tags=['buildset:2'],
    )
    self.put_build(different_buildset)

    different_bucket = model.Build(
        bucket='another bucket',
        tags=[self.INDEXED_TAG],
    )
    self.put_build(different_bucket)

    self.mock_cannot(user.Action.SEARCH_BUILDS, 'secret.bucket')
    builds, _ = self.search(
        tags=[self.INDEXED_TAG], buckets=[self.test_build.bucket]
    )
    self.assertEqual(builds, [self.test_build])

  def test_search_with_dup_tag_entries(self):
    self.test_build.tags = [self.INDEXED_TAG]
    self.test_build.put()

    entry = search.TagIndexEntry(
        bucket=self.test_build.bucket,
        build_id=self.test_build.key.id(),
    )
    search.TagIndex(
        id=self.INDEXED_TAG,
        entries=[entry, entry],
    ).put()

    builds, _ = self.search(
        buckets=[self.test_build.bucket], tags=[self.INDEXED_TAG]
    )
    self.assertEqual(builds, [self.test_build])

  def test_search_with_incomplete_index(self):
    self.test_build.tags = [self.INDEXED_TAG]
    self.test_build.put()

    self.put_many_builds(10)  # add unrelated builds

    search.TagIndex(id=self.INDEXED_TAG, permanently_incomplete=True).put()

    builds, _ = self.search(
        buckets=[self.test_build.bucket], tags=[self.INDEXED_TAG]
    )
    self.assertEqual(builds, [self.test_build])

    with self.assertRaises(errors.TagIndexIncomplete):
      self.search(
          buckets=[self.test_build.bucket],
          tags=[self.INDEXED_TAG],
          start_cursor='id>0'
      )

  def test_search_with_no_tag_index(self):
    builds, _ = self.search()
    self.assertEqual(builds, [])

  def test_search_with_inconsistent_entries(self):
    self.put_build(self.test_build)

    will_be_deleted = model.Build(
        bucket=self.test_build.bucket, tags=[self.INDEXED_TAG]
    )
    self.put_build(will_be_deleted)  # updates index
    will_be_deleted.key.delete()

    buildset_will_change = model.Build(
        bucket=self.test_build.bucket, tags=[self.INDEXED_TAG]
    )
    self.put_build(buildset_will_change)  # updates index
    buildset_will_change.tags = []
    buildset_will_change.put()

    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [self.test_build])

  def test_search_with_tag_index_cursor(self):
    builds = self.put_many_builds(10)
    builds.reverse()
    res, cursor = self.search(
        tags=[self.INDEXED_TAG], start_cursor='id>%d' % builds[-1].key.id()
    )
    self.assertEqual(res, [])
    self.assertIsNone(cursor)

    builds = self.put_many_builds(10, tags=[self.INDEXED_TAG])
    builds.reverse()
    res, cursor = self.search(
        tags=[self.INDEXED_TAG],
        buckets=[self.test_build.bucket],
        create_time_low=builds[5].create_time,
        start_cursor='id>%d' % builds[7].key.id()
    )
    self.assertEqual(res, [])
    self.assertIsNone(cursor)

    res, cursor = self.search(
        tags=[self.INDEXED_TAG],
        buckets=[self.test_build.bucket],
        create_time_high=builds[7].create_time,
        start_cursor='id>%d' % builds[5].key.id()
    )
    # create_time_high is exclusive
    self.assertEqual(res, builds[8:])
    self.assertIsNone(cursor)

  def test_search_with_tag_index_cursor_but_no_inded_tag(self):
    with self.assertRaises(errors.InvalidInputError):
      self.search(start_cursor='id>1')

  def test_search_with_experimental(self):
    self.put_build(self.test_build)
    build2 = model.Build(
        id=self.test_build.key.id() - 1,  # newer
        bucket=self.test_build.bucket,
        tags=self.test_build.tags,
        experimental=True,
    )
    self.put_build(build2)

    builds, _ = self.search(buckets=[self.test_build.bucket])
    self.assertEqual(builds, [self.test_build])
    builds, _ = self.search(
        buckets=[self.test_build.bucket], tags=[self.INDEXED_TAG]
    )
    self.assertEqual(builds, [self.test_build])

    builds, _ = self.search(
        buckets=[self.test_build.bucket], include_experimental=True
    )
    self.assertEqual(builds, [build2, self.test_build])
    builds, _ = self.search(
        buckets=[self.test_build.bucket],
        tags=[self.INDEXED_TAG],
        include_experimental=True
    )
    self.assertEqual(builds, [build2, self.test_build])

  def test_multiple_shard_of_tag_index(self):
    # Add two builds into shard0 and 2 in shard1.
    search.TagIndex.random_shard_index.side_effect = [0, 0, 1, 1]
    shard0_builds = self.put_many_builds(2, tags=[self.INDEXED_TAG])
    shard1_builds = self.put_many_builds(2, tags=[self.INDEXED_TAG])

    shard0 = search.TagIndex.make_key(0, self.INDEXED_TAG).get()
    shard1 = search.TagIndex.make_key(1, self.INDEXED_TAG).get()

    self.assertEqual({e.build_id for e in shard0.entries},
                     {b.key.id() for b in shard0_builds})
    self.assertEqual({e.build_id for e in shard1.entries},
                     {b.key.id() for b in shard1_builds})

    # Retrieve all builds from tag indexes.
    expected = sorted(shard0_builds + shard1_builds, key=lambda b: b.key.id())
    actual, _ = self.search(
        buckets=[self.test_build.bucket], tags=[self.INDEXED_TAG]
    )
    self.assertEqual(expected, actual)

  def test_bad_cursor(self):
    with self.assertRaises(errors.InvalidInputError):
      self.search(
          buckets=[self.test_build.bucket],
          start_cursor='a bad cursor',
      )

  def test_no_permissions(self):
    user.can_async.return_value = future(False)
    with self.assertRaises(auth.AuthorizationError):
      self.search(buckets=['chromium'])


class TagIndexTest(testing.AppengineTestCase):

  def test_zeroth_shard(self):
    self.assertEqual(
        search.TagIndex.make_key(0, 'a:b'),
        ndb.Key(search.TagIndex, 'a:b'),
    )

  def test_positive_shard_index(self):
    self.assertEqual(
        search.TagIndex.make_key(1, 'a:b'),
        ndb.Key(search.TagIndex, ':1:a:b'),
    )

  def test_random_shard_key(self):
    with mock.patch('search.TagIndex.random_shard_index', return_value=2):
      self.assertEqual(
          search.TagIndex.random_shard_key('a:b'),
          ndb.Key(search.TagIndex, ':2:a:b'),
      )


class TagIndexMaintenanceTest(testing.AppengineTestCase):

  def setUp(self):
    super(TagIndexMaintenanceTest, self).setUp()
    self.patch('search.TagIndex.random_shard_index', return_value=0)

  def test_add_too_many_to_index(self):
    limit = search.TagIndex.MAX_ENTRY_COUNT
    entries = [
        search.TagIndexEntry(build_id=i, bucket='x') for i in xrange(limit * 2)
    ]
    tag = 'a:b'
    index_key = search.TagIndex.make_key(0, tag)

    search.add_to_tag_index_async(tag, entries[:limit]).get_result()
    self.assertFalse(index_key.get().permanently_incomplete)

    search.add_to_tag_index_async(tag, entries[limit:]).get_result()
    self.assertTrue(index_key.get().permanently_incomplete)

    search.add_to_tag_index_async(tag, entries[limit:]).get_result()
    self.assertTrue(index_key.get().permanently_incomplete)

  def test_update_tag_indexes_async(self):
    builds = [
        model.Build(
            id=1,
            bucket='chromium',
            tags=['buildset:1', 'buildset:2'],
        ),
        model.Build(
            id=2,
            bucket='v8',
            tags=['buildset:2'],
        ),
    ]
    ndb.Future.wait_all(search.update_tag_indexes_async(builds))

    self.assertEqual(
        {e.build_id for e in search.TagIndex.get_by_id('buildset:1').entries},
        {1},
    )
    self.assertEqual(
        {e.build_id for e in search.TagIndex.get_by_id('buildset:2').entries},
        {1, 2},
    )
