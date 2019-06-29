# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

from google.appengine.ext import ndb

from components import auth
from testing_utils import testing

from proto import common_pb2
from proto import project_config_pb2
from test import test_util
from test.test_util import future
import errors
import model
import search
import user


class ValidateQueryTests(testing.AppengineTestCase):

  def test_two_ranges(self):
    q = search.Query(
        create_time_low=datetime.datetime(2018, 1, 1),
        build_high=1000,
    )
    err_pattern = r'mutually exclusive'
    with self.assertRaisesRegexp(errors.InvalidInputError, err_pattern):
      q.validate()

  def test_project_and_bucket_ids(self):
    q = search.Query(project='chromium', bucket_ids=['chromium/try'])
    err_pattern = r'mutually exclusive'
    with self.assertRaisesRegexp(errors.InvalidInputError, err_pattern):
      q.validate()

  def test_builder_without_bucket(self):
    q = search.Query(builder='linux-rel')
    err_pattern = r'builder requires non-empty bucket_ids'
    with self.assertRaisesRegexp(errors.InvalidInputError, err_pattern):
      q.validate()


class SearchTest(testing.AppengineTestCase):
  INDEXED_TAG = test_util.INDEXED_TAG_STRING

  def setUp(self):
    super(SearchTest, self).setUp()

    self.current_identity = auth.Identity('service', 'unittest')
    self.patch(
        'components.auth.get_current_identity',
        side_effect=lambda: self.current_identity
    )
    self.patch('user.can_async', return_value=future(True))
    self.now = datetime.datetime(2015, 1, 1)
    self.patch('components.utils.utcnow', side_effect=lambda: self.now)

    self.chromium_try = project_config_pb2.Bucket(name='try')

    self.patch(
        'config.get_bucket_async',
        return_value=future({'deadbeef': self.chromium_try})
    )
    self.patch(
        'user.get_accessible_buckets_async',
        autospec=True,
        return_value=future({'chromium/try'}),
    )
    self.patch('search.TagIndex.random_shard_index', return_value=0)

  def mock_cannot(self, action, bucket_id=None):

    def can_async(requested_bucket_id, requested_action, _identity=None):
      match = (
          requested_action == action and
          (bucket_id is None or requested_bucket_id == bucket_id)
      )
      return future(not match)

    # user.can_async is patched in setUp()
    user.can_async.side_effect = can_async

  def put_many_builds(self, count=100, **build_proto_fields):
    return [self.put_build(**build_proto_fields) for _ in xrange(count)]

  def put_build(self, **build_proto_fields):
    """Puts a build and updates tag index."""
    build_proto_fields.setdefault('id', model.create_build_ids(self.now, 1)[0])
    self.now += datetime.timedelta(seconds=1)

    build = test_util.build(**build_proto_fields)
    build.put()

    index_entry = search.TagIndexEntry(
        build_id=build.key.id(),
        bucket_id=build.bucket_id,
    )
    for t in search.indexed_tags(build.tags):
      search.add_to_tag_index_async(t, [index_entry]).get_result()
    return build

  def search(self, **query_attrs):
    return search.search_async(search.Query(**query_attrs)).get_result()

  def assert_equal_keys(self, first, second):
    keys = lambda builds: [b.key for b in builds]
    self.assertEqual(keys(first), keys(second))

  def test_without_buckets(self):
    self.mock_cannot(user.Action.SEARCH_BUILDS, 'chromium/ci')

    build1 = self.put_build(builder=dict(bucket='try'))
    build2 = self.put_build(builder=dict(bucket='ci'))

    builds, _ = self.search()
    self.assertEqual(builds, [build1])
    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [build1])

    # All buckets are available.
    user.get_accessible_buckets_async.return_value = future(None)
    user.can_async.side_effect = None
    builds, _ = self.search()
    self.assertEqual(builds, [build2, build1])
    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [build2, build1])

    # No buckets are available.
    user.get_accessible_buckets_async.return_value = future(set())
    self.mock_cannot(user.Action.SEARCH_BUILDS)
    builds, _ = self.search()
    self.assertEqual(builds, [])
    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [])

  def test_auth_error(self):
    self.mock_cannot(user.Action.SEARCH_BUILDS)
    with self.assertRaises(auth.AuthorizationError):
      self.search(bucket_ids=['chromium/try'])

  def test_filter_by_tag(self):
    build = self.put_build(tags=[dict(key='t', value='0')])
    self.put_build()

    builds, _ = self.search(tags=['t:0'])
    self.assertEqual(builds, [build])

  def test_filter_by_many_tags(self):
    build1 = self.put_build(
        tags=[
            test_util.INDEXED_TAG,
            dict(key='t', value='0'),
            dict(key='t', value='1'),
        ]
    )
    self.put_build(tags=[
        test_util.INDEXED_TAG,
        dict(key='t', value='0'),
    ])

    # Search by both tags.
    builds, _ = self.search(tags=[self.INDEXED_TAG, 't:0', 't:1'],)
    self.assertEqual(builds, [build1])

    builds, _ = self.search(tags=['t:0', 't:1'])
    self.assertEqual(builds, [build1])

  def test_filter_by_build_address(self):
    build = self.put_build(
        tags=[dict(key='build_address', value='chromium/infra/1')]
    )

    builds, _ = self.search(tags=['build_address:chromium/infra/1'])
    self.assertEqual(builds, [build])

  def test_filter_by_project(self):
    user.get_accessible_buckets_async.return_value = future({
        'chromium/try', 'v8/try'
    })
    build = self.put_build(builder=dict(project='chromium'))
    self.put_build(builder=dict(project='v8'))

    builds, _ = self.search(project='chromium')
    self.assertEqual(builds, [build])

  def test_filter_by_bucket(self):
    build1 = self.put_build(builder=dict(project='chromium', bucket='1'))
    self.put_build(builder=dict(project='chromium', bucket='2'))

    builds, _ = self.search(bucket_ids=['chromium/1'])
    self.assertEqual(builds, [build1])

  def test_filter_by_builder(self):
    build1 = self.put_build(
        builder=dict(project='chromium', bucket='try', builder='linux-rel')
    )
    self.put_build(
        builder=dict(project='chromium', bucket='try', builder='mac-rel')
    )
    self.put_build(
        builder=dict(project='chromium', bucket='ci', builder='linux-rel')
    )

    builds, _ = self.search(bucket_ids=['chromium/try'], builder='linux-rel')
    self.assertEqual(builds, [build1])

  def test_filter_by_project_admin(self):
    user.get_accessible_buckets_async.return_value = future(None)
    build = self.put_build(builder=dict(project='chromium'))
    self.put_build(builder=dict(project='v8'))

    builds, _ = self.search(project='chromium')
    self.assertEqual(builds, [build])

  def test_filter_by_project_indexed(self):
    build1 = self.put_build(builder=dict(project='1'))
    self.put_build(builder=dict(project='2'))

    builds, _ = self.search(
        project='1',
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [build1])

  def test_filter_by_status_legacy(self):
    scheduled_build = self.put_build(status=common_pb2.SCHEDULED)
    self.put_build(status=common_pb2.SUCCESS)

    builds, _ = self.search(status=search.StatusFilter.SCHEDULED)
    self.assertEqual(builds, [scheduled_build])
    builds, _ = self.search(
        status=search.StatusFilter.SCHEDULED, tags=[self.INDEXED_TAG]
    )
    self.assertEqual(builds, [scheduled_build])

    builds, _ = self.search(
        status=search.StatusFilter.COMPLETED,
        result=model.BuildResult.FAILURE,
        tags=[self.INDEXED_TAG]
    )
    self.assertEqual(builds, [])
    builds, _ = self.search(
        status=search.StatusFilter.COMPLETED, result=model.BuildResult.FAILURE
    )
    self.assertEqual(builds, [])

    builds, _ = self.search(status=search.StatusFilter.INCOMPLETE)
    self.assertEqual(builds, [scheduled_build])
    builds, _ = self.search(
        status=search.StatusFilter.INCOMPLETE, tags=[self.INDEXED_TAG]
    )
    self.assertEqual(builds, [scheduled_build])

  def test_filter_by_status(self):
    scheduled_build = self.put_build(status=common_pb2.SCHEDULED)
    self.put_build(status=common_pb2.STARTED)

    builds, _ = self.search(status=common_pb2.SCHEDULED)
    self.assertEqual(builds, [scheduled_build])
    builds, _ = self.search(
        status=common_pb2.SCHEDULED, tags=[self.INDEXED_TAG]
    )
    self.assertEqual(builds, [scheduled_build])

    builds, _ = self.search(status=common_pb2.FAILURE, tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [])
    builds, _ = self.search(status=common_pb2.FAILURE)
    self.assertEqual(builds, [])

  def test_filter_by_created_by(self):
    build1 = self.put_build(created_by='user:1@example.com')
    self.put_build(created_by='user:2@example.com')

    builds, _ = self.search(created_by='1@example.com')
    self.assertEqual(builds, [build1])
    builds, _ = self.search(
        created_by='1@example.com',
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [build1])

  def test_filter_by_build_id_range_lo(self):
    builds = self.put_many_builds(count=5)
    # make builds order same as search results order
    builds.reverse()

    actual, _ = self.search(build_low=builds[0].key.id())
    self.assert_equal_keys(builds, actual)

    actual, _ = self.search(build_low=builds[0].key.id() + 1)
    self.assert_equal_keys(builds[1:], actual)

  def test_filter_by_build_id_range_hi(self):
    builds = self.put_many_builds(count=5)
    # make builds order same as search results order
    builds.reverse()

    actual, _ = self.search(build_high=builds[-1].key.id())
    self.assert_equal_keys(builds[:-1], actual)

    actual, _ = self.search(build_high=builds[-1].key.id() + 1)
    self.assert_equal_keys(builds, actual)

  def test_filter_by_creation_time_range(self):
    too_old = model.BEGINING_OF_THE_WORLD - datetime.timedelta(milliseconds=1)
    old_time = datetime.datetime(2010, 2, 4)
    new_time = datetime.datetime(2012, 2, 4)

    old_build = self.put_build(
        id=model.create_build_ids(old_time, 1)[0],
        create_time=test_util.dt2ts(old_time),
    )
    new_build = self.put_build(
        id=model.create_build_ids(new_time, 1)[0],
        create_time=test_util.dt2ts(new_time),
    )

    # Test lower bound

    builds, _ = self.search(create_time_low=too_old)
    self.assertEqual(builds, [new_build, old_build])

    builds, _ = self.search(create_time_low=old_time)
    self.assertEqual(builds, [new_build, old_build])

    builds, _ = self.search(
        create_time_low=old_time,
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [new_build, old_build])

    builds, _ = self.search(create_time_low=new_time)
    self.assertEqual(builds, [new_build])

    builds, _ = self.search(
        create_time_low=new_time,
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [new_build])

    # Test upper bound

    builds, _ = self.search(create_time_high=too_old)
    self.assertEqual(builds, [])

    builds, _ = self.search(create_time_high=old_time)
    self.assertEqual(builds, [])

    builds, _ = self.search(
        create_time_high=old_time,
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [])

    builds, _ = self.search(create_time_high=new_time)
    self.assertEqual(builds, [old_build])
    builds, _ = self.search(
        create_time_high=new_time,
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [old_build])

    builds, _ = self.search(
        create_time_high=(new_time + datetime.timedelta(milliseconds=1)),
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [new_build, old_build])

    # Test both sides bounded

    builds, _ = self.search(
        create_time_low=new_time,
        create_time_high=old_time,
    )
    self.assertEqual(builds, [])

    builds, _ = self.search(
        create_time_low=old_time,
        create_time_high=new_time,
    )
    self.assertEqual(builds, [old_build])

    builds, _ = self.search(
        create_time_low=old_time,
        create_time_high=new_time,
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [old_build])

    # Test reversed bounds

    builds, _ = self.search(
        create_time_low=new_time,
        create_time_high=old_time,
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [])

  def test_filter_by_retry_of(self):
    build1 = self.put_build()
    build1.retry_of = 42
    build1.put()

    build2 = self.put_build()
    build2.retry_of = 43
    build2.put()

    builds, _ = self.search(retry_of=42)
    self.assertEqual(builds, [build1])
    builds, _ = self.search(retry_of=42, tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [build1])

  def test_filter_by_retry_of_and_buckets(self):
    self.put_build(id=42, builder=dict(bucket='try'))

    build1 = self.put_build(builder=dict(bucket='try'))
    build1.retry_of = 42
    build1.put()

    build2 = self.put_build(builder=dict(bucket='ci'))
    build2.retry_of = 42
    build2.put()

    builds, _ = self.search(retry_of=42)
    self.assertEqual(builds, [build1])
    builds, _ = self.search(
        retry_of=42,
        tags=[self.INDEXED_TAG],
    )
    self.assertEqual(builds, [build1])

  def test_filter_by_retry_of_with_auth_error(self):
    self.mock_cannot(user.Action.SEARCH_BUILDS, bucket_id='chromium/try')
    orig_build = self.put_build(id=1)
    retried_build = self.put_build(id=1)
    retried_build.retry_of = orig_build.key.id()
    retried_build.put()

    with self.assertRaises(auth.AuthorizationError):
      # The build we are looking for was a retry of a build that is in a bucket
      # that we don't have access to.
      self.search(retry_of=1)
    with self.assertRaises(auth.AuthorizationError):
      # The build we are looking for was a retry of a build that is in a bucket
      # that we don't have access to.
      self.search(retry_of=1, tags=[self.INDEXED_TAG])

  def test_filter_by_created_by_with_bad_string(self):
    with self.assertRaises(errors.InvalidInputError):
      self.search(created_by='blah')

  def test_filter_by_with_paging_using_datastore_query(self):
    self.put_many_builds()

    first_page, next_cursor = self.search(max_builds=10)
    self.assertEqual(len(first_page), 10)
    self.assertTrue(next_cursor)

    second_page, _ = self.search(max_builds=10, start_cursor=next_cursor)
    self.assertEqual(len(second_page), 10)
    # no cover due to a bug in coverage (http://stackoverflow.com/a/35325514)
    self.assertTrue(any(new not in first_page for new in second_page)
                   )  # pragma: no cover

  def test_filter_by_with_paging_using_tag_index(self):
    self.put_many_builds(20)

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

  def test_filter_by_with_bad_tags(self):

    def test_bad_tag(tags):
      with self.assertRaises(errors.InvalidInputError):
        self.search(tags=tags)

    test_bad_tag(['x'])
    test_bad_tag([1])
    test_bad_tag({})
    test_bad_tag(1)

  def test_filter_by_with_non_number_max_builds(self):
    with self.assertRaises(errors.InvalidInputError):
      self.search(tags=['a:b'], max_builds='a')

  def test_filter_by_with_negative_max_builds(self):
    with self.assertRaises(errors.InvalidInputError):
      self.search(tags=['a:b'], max_builds=-2)

  def test_filter_by_indexed_tag(self):
    self.mock_cannot(user.Action.SEARCH_BUILDS, 'secret/secret.bucket')

    self.put_build(builder=dict(project='chromium', bucket='try'),)
    self.put_build(builder=dict(project='chromium', bucket='secret'),)
    build = self.put_build(
        builder=dict(project='chromium', bucket='try'),
        tags=[dict(key='buildset', value='2')]
    )

    builds, _ = self.search(tags=['buildset:2'], bucket_ids=['chromium/try'])
    self.assertEqual(builds, [build])

  def test_filter_by_indexed_tag_builder(self):
    build = self.put_build(
        builder=dict(project='chromium', bucket='try', builder='linux-rel'),
        tags=[dict(key='buildset', value='2')]
    )
    self.put_build(
        builder=dict(project='chromium', bucket='try', builder='mac-rel'),
        tags=[dict(key='buildset', value='2')]
    )

    builds, _ = self.search(
        tags=['buildset:2'], bucket_ids=['chromium/try'], builder='linux-rel'
    )
    self.assertEqual(builds, [build])

  def test_filter_by_with_dup_tag_entries(self):
    build = test_util.build(id=1)
    build.put()

    entry = search.TagIndexEntry(build_id=1, bucket_id='chromium/try')
    search.TagIndex(
        id=self.INDEXED_TAG,
        entries=[entry, entry],
    ).put()

    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [build])

  def test_filter_by_with_incomplete_index(self):
    build = self.put_build(builder=dict(bucket='try'))
    self.put_many_builds(10, builder=dict(bucket='ci'))  # add unrelated builds

    search.TagIndex(id=self.INDEXED_TAG, permanently_incomplete=True).put()

    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [build])

    with self.assertRaises(errors.TagIndexIncomplete):
      self.search(tags=[self.INDEXED_TAG], start_cursor='id>0')

  def test_filter_by_with_legacy_index(self):
    build = test_util.build(id=1)
    build.put()

    idx = search.TagIndex(
        id=self.INDEXED_TAG,
        entries=[
            search.TagIndexEntry(build_id=1),
            # this entry will be deleted, because bucket_id could not be
            # resolved.
            search.TagIndexEntry(build_id=123),
        ],
    )
    idx.put()

    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [build])

    idx = idx.key.get()
    self.assertEqual(len(idx.entries), 1)
    self.assertEqual(idx.entries[0].bucket_id, 'chromium/try')

  def test_filter_by_with_no_tag_index(self):
    builds, _ = self.search()
    self.assertEqual(builds, [])

  def test_filter_by_with_inconsistent_entries(self):
    build = self.put_build()

    will_be_deleted = self.put_build()
    # index is updated.
    will_be_deleted.key.delete()

    buildset_will_change = self.put_build()
    # index is updated.
    buildset_will_change.tags = []
    buildset_will_change.put()

    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [build])

  def test_filter_by_with_tag_index_cursor(self):
    builds = self.put_many_builds(10)
    builds.reverse()
    res, cursor = self.search(
        tags=[self.INDEXED_TAG], start_cursor='id>%d' % builds[-1].key.id()
    )
    self.assertEqual(res, [])
    self.assertIsNone(cursor)

    builds = self.put_many_builds(10, tags=[dict(key='buildset', value='2')])
    builds.reverse()
    res, cursor = self.search(
        tags=['buildset:2'],
        create_time_low=builds[5].create_time,
        start_cursor='id>%d' % builds[7].key.id()
    )
    self.assertEqual(res, [])
    self.assertIsNone(cursor)

    res, cursor = self.search(
        tags=['buildset:2'],
        create_time_high=builds[7].create_time,
        start_cursor='id>%d' % builds[5].key.id()
    )
    # create_time_high is exclusive
    self.assertEqual(res, builds[8:])
    self.assertIsNone(cursor)

  def test_filter_by_with_tag_index_cursor_but_no_inded_tag(self):
    with self.assertRaises(errors.InvalidInputError):
      self.search(start_cursor='id>1')

  def test_filter_by_with_experimental(self):
    exp_build = self.put_build(input=dict(experimental=True))
    prod_build = self.put_build(input=dict(experimental=False))

    builds, _ = self.search()
    self.assertEqual(builds, [prod_build])
    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [prod_build])

    builds, _ = self.search(include_experimental=True)
    self.assertEqual(builds, [prod_build, exp_build])
    builds, _ = self.search(tags=[self.INDEXED_TAG], include_experimental=True)
    self.assertEqual(builds, [prod_build, exp_build])

  def test_filter_by_with_experimental_and_paging(self):
    for _ in xrange(100):
      self.put_build(input=dict(experimental=True))
    prod_build = self.put_build(input=dict(experimental=False))
    for _ in xrange(100):
      self.put_build(input=dict(experimental=True))

    builds, _ = self.search()
    self.assertEqual(builds, [prod_build])
    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [prod_build])

  def test_multiple_shard_of_tag_index(self):
    # Add two builds into shard0 and 2 in shard1.
    search.TagIndex.random_shard_index.return_value = 0
    shard0_builds = self.put_many_builds(2)
    search.TagIndex.random_shard_index.return_value = 1
    shard1_builds = self.put_many_builds(2)

    shard0 = search.TagIndex.make_key(0, self.INDEXED_TAG).get()
    shard1 = search.TagIndex.make_key(1, self.INDEXED_TAG).get()

    self.assertEqual({e.build_id for e in shard0.entries},
                     {b.key.id() for b in shard0_builds})
    self.assertEqual({e.build_id for e in shard1.entries},
                     {b.key.id() for b in shard1_builds})

    # Retrieve all builds from tag indexes.
    expected = sorted(shard0_builds + shard1_builds, key=lambda b: b.key.id())
    actual, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(expected, actual)

  def test_bad_cursor(self):
    with self.assertRaises(errors.InvalidInputError):
      self.search(start_cursor='a bad cursor',)

  def test_no_permissions(self):
    user.can_async.return_value = future(False)
    with self.assertRaises(auth.AuthorizationError):
      self.search(bucket_ids=['chromium/try'])


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
        search.TagIndexEntry(build_id=i, bucket_id='chromium/try')
        for i in xrange(limit * 2)
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
        test_util.build(
            id=1,
            builder=dict(project='chromium'),
            tags=[
                dict(key='buildset', value='common'),
                dict(key='buildset', value='unique'),
            ]
        ),
        test_util.build(
            id=2,
            builder=dict(project='v8'),
            tags=[
                dict(key='buildset', value='common'),
            ]
        ),
    ]
    ndb.Future.wait_all(search.update_tag_indexes_async(builds))

    common = search.TagIndex.get_by_id('buildset:common')
    self.assertEqual(
        {e.build_id for e in common.entries},
        {1, 2},
    )

    unique = search.TagIndex.get_by_id('buildset:unique')
    self.assertEqual(
        {e.build_id for e in unique.entries},
        {1},
    )
