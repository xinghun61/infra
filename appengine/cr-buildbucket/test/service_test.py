# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime
import json

from components import auth
from components import net
from components import utils
from google.appengine.ext import ndb
from testing_utils import testing
import mock

from proto import project_config_pb2
from test.test_util import future
import acl
import api_common
import config
import errors
import events
import model
import service
import swarming


class BuildBucketServiceTest(testing.AppengineTestCase):
  INDEXED_TAG = 'buildset:1'

  def __init__(self, *args, **kwargs):
    super(BuildBucketServiceTest, self).__init__(*args, **kwargs)
    self.test_build = None

  def setUp(self):
    super(BuildBucketServiceTest, self).setUp()
    self.patch(
        'service._log_inconsistent_search_results', side_effect=self.fail)

    self.current_identity = auth.Identity('service', 'unittest')
    self.patch(
        'components.auth.get_current_identity',
        side_effect=lambda: self.current_identity)
    self.patch('acl.can_async', return_value=future(True))
    self.patch(
        'acl.get_available_buckets', autospec=True,
        return_value=['chromium'])
    self.now = datetime.datetime(2015, 1, 1)
    self.patch('components.utils.utcnow', side_effect=lambda: self.now)

    self.chromium_bucket = project_config_pb2.Bucket(name='chromium')
    self.chromium_project_id = 'test'
    self.chromium_swarming = project_config_pb2.Swarming(
        hostname='chromium-swarm.appspot.com',
        builders=[
          project_config_pb2.Builder(
              name='infra',
              dimensions=['pool:default'],
              recipe=project_config_pb2.Builder.Recipe(
                repository='https://example.com',
                name='presubmit',
              ),
          ),
        ],
    )
    self.patch(
        'config.get_bucket_async',
        return_value=future(('project', self.chromium_bucket)))
    self.patch('swarming.create_task_async', return_value=future(None))
    self.patch('swarming.cancel_task_async', return_value=future(None))

    self.test_build = model.Build(
        id=model.create_build_id(self.now),
        bucket='chromium',
        project=self.chromium_project_id,
        create_time=self.now,
        tags=[self.INDEXED_TAG],
        parameters={
          'builder_name': 'infra',
          'changes': [{
            'author': 'nodir@google.com',
            'message': 'buildbucket: initial commit'
          }]
        },
        canary=False,
    )

    self.patch(
        'google.appengine.api.app_identity.get_default_version_hostname',
        autospec=True,
        return_value='buildbucket.example.com')

    self.patch(
        'events.enqueue_tasks_async', autospec=True, return_value=future(None))

  def mock_cannot(self, action, bucket=None):
    def can_async(requested_bucket, requested_action, _identity=None):
      match = (
        requested_action == action and
        (bucket is None or requested_bucket == bucket))
      return future(not match)

    # acl.can_async is patched in setUp()
    acl.can_async.side_effect = can_async

  def put_many_builds(self, count=100, tags=None):
    tags = tags or []
    builds = []
    for _ in xrange(count):
      b = model.Build(
          id=model.create_build_id(self.now),
          bucket=self.test_build.bucket,
          tags=tags,
          create_time=self.now)
      self.now += datetime.timedelta(seconds=1)
      self.put_build(b)
      builds.append(b)
    return builds

  def put_build(self, build):
    """Puts a build and updates tag index."""
    build.put()

    index_entry = model.TagIndexEntry(
        bucket=build.bucket,
        build_id=build.key.id(),
    )
    for t in service._indexed_tags(build.tags):
      service._add_to_tag_index_async(t, [index_entry]).get_result()

  #################################### ADD #####################################

  def add(self, bucket, **request_fields):
    return service.add(
        service.BuildRequest(
            self.chromium_project_id,
            bucket,
            **request_fields
        )
    )

  def test_add(self):
    params = {'buildername': 'linux_rel'}
    build = self.add(
        bucket='chromium',
        parameters=params,
        canary_preference=model.CanaryPreference.CANARY,
    )
    self.assertIsNotNone(build.key)
    self.assertIsNotNone(build.key.id())
    self.assertEqual(build.bucket, 'chromium')
    self.assertEqual(build.parameters, params)
    self.assertEqual(build.created_by, auth.get_current_identity())
    self.assertEqual(build.canary_preference, model.CanaryPreference.CANARY)

  def test_add_with_client_operation_id(self):
    build = self.add(
      bucket='chromium',
      parameters={'builder_name': 'linux_rel'},
      client_operation_id='1',
    )
    build2 = self.add(
      bucket='chromium',
      parameters={'builder_name': 'linux_rel'},
      client_operation_id='1',
    )
    self.assertIsNotNone(build.key)
    self.assertEqual(build, build2)

  def test_add_with_bad_bucket_name(self):
    with self.assertRaises(errors.InvalidInputError):
      self.add(bucket='chromium as')
    with self.assertRaises(errors.InvalidInputError):
      self.add(bucket='')

  def test_add_with_bad_canary_preference(self):
    with self.assertRaises(errors.InvalidInputError):
      self.add(bucket='bucket', canary_preference=None)

  def test_add_with_leasing(self):
    build = self.add(
      bucket='chromium',
      lease_expiration_date=utils.utcnow() + datetime.timedelta(seconds=10),
    )
    self.assertTrue(build.is_leased)
    self.assertGreater(build.lease_expiration_date, utils.utcnow())
    self.assertIsNotNone(build.lease_key)

  def test_add_with_auth_error(self):
    self.mock_cannot(acl.Action.ADD_BUILD)
    with self.assertRaises(auth.AuthorizationError):
      self.add(bucket=self.test_build.bucket)

  def test_add_with_bad_parameters(self):
    with self.assertRaises(errors.InvalidInputError):
      self.add(bucket='bucket', parameters=[])

  def test_add_with_swarming_400(self):
    self.chromium_bucket.swarming.MergeFrom(self.chromium_swarming)
    swarming.create_task_async.side_effect = net.Error(
        '', status_code=400, response='bad request')
    with self.assertRaises(errors.InvalidInputError):
      self.add(bucket=self.test_build.bucket)

  def test_add_with_swarming_200_and_400(self):
    self.chromium_bucket.swarming.MergeFrom(self.chromium_swarming)

    def create_task_async(b):
      if b.parameters['i'] == 1:
        raise net.Error('', status_code=400, response='bad request')
      b.swarming_hostname = self.chromium_bucket.swarming.hostname
      b.swarming_task_id = 'deadbeef'

    swarming.create_task_async.side_effect = create_task_async

    with self.assertRaises(errors.InvalidInputError):
      service.add_many_async([
        service.BuildRequest(
            project=self.chromium_project_id,
            bucket=self.chromium_bucket.name,
            parameters={'builder_name': 'infra', 'i': 0},
        ),
        service.BuildRequest(
            project=self.chromium_project_id,
            bucket=self.chromium_bucket.name,
            parameters={'builder_name': 'infra', 'i': 1},
        )
      ]).get_result()
    swarming.cancel_task_async.assert_called_with(
        self.chromium_bucket.swarming.hostname, 'deadbeef')

  def test_add_with_swarming_403(self):
    self.chromium_bucket.swarming.MergeFrom(self.chromium_swarming)
    swarming.create_task_async.side_effect = net.AuthError(
      '', status_code=403, response='access denied')
    with self.assertRaises(auth.AuthorizationError):
      self.add(bucket=self.test_build.bucket)

  def test_add_with_builder_name(self):
    build = self.add(
      bucket='chromium',
      parameters={'builder_name': 'linux_rel'},
      client_operation_id='1',
    )
    self.assertTrue('builder:linux_rel' in build.tags)

  def test_validate_tags_none(self):
    self.assertIsNone(service.validate_tags(None, 'search'))

  def test_validate_tags_nonlist(self):
    with self.assertRaises(errors.InvalidInputError):
      service.validate_tags('tag:value', 'search')

  def test_validate_tags_nonstring(self):
    with self.assertRaises(errors.InvalidInputError):
      service.validate_tags(['tag:value', 123456], 'search')

  def test_validate_tags_no_colon(self):
    with self.assertRaises(errors.InvalidInputError):
      service.validate_tags(['tag,value'], 'search')

  def test_validate_tags_build_address(self):
    with self.assertRaises(errors.InvalidInputError):
      service.validate_tags(['build_address:1'], 'new')
    with self.assertRaises(errors.InvalidInputError):
      service.validate_tags(['build_address:1'], 'append')

  def test_validate_tags_append_builder(self):
    with self.assertRaises(errors.InvalidInputError):
      service.validate_tags(['builder:1'], 'append')

  def test_validate_tags_no_key(self):
    with self.assertRaises(errors.InvalidInputError):
      service.validate_tags([':'], 'search')

  def test_validate_buildset(self):
    service.validate_build_set(
        'commit/gitiles/chromium.googlesource.com/chromium/src/+/'
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    )
    service.validate_build_set(
      'patch/gerrit/chromium-review.googlesource.com/123/456'
    )

    service.validate_build_set(
        'patch/gerrit/chromium-review.googlesource.com/aa/bb'
    )

    bad = [
      ('commit/gitiles/chromium.googlesource.com/a/chromium/src/+/'
       'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'),
      ('commit/gitiles/chromium.googlesource.com/chromium/src.git/+/'
       'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'),
      'commit/gitiles/chromium.googlesource.com/chromium/src.git/+/aaaaaaaa',
    ]
    for bs in bad:
      with self.assertRaises(errors.InvalidInputError):
        service.validate_build_set(bs)

  def test_add_builder_tag(self):
    build = service.add(service.BuildRequest(
        project=self.chromium_project_id,
        bucket='chromium',
        parameters={'builder_name': 'foo'}
    ))
    self.assertEqual(build.tags, ['builder:foo'])

  def test_add_builder_tag_multi(self):
    build = service.add(service.BuildRequest(
        project=self.chromium_project_id,
        bucket='chromium',
        parameters={'builder_name': 'foo'},
        tags=['builder:foo', 'builder:foo'],
    ))
    self.assertEqual(build.tags, ['builder:foo'])

  def test_add_builder_tag_different(self):
    with self.assertRaises(errors.InvalidInputError):
      service.add(service.BuildRequest(
          project=self.chromium_project_id,
          bucket='chromium',
          tags=['builder:foo', 'builder:bar'],
      ))

  def test_add_builder_tag_coincide(self):
    build = service.add(service.BuildRequest(
        project=self.chromium_project_id,
        bucket='chromium',
        parameters={'builder_name': 'foo'},
        tags=['builder:foo'],
    ))
    self.assertEqual(build.tags, ['builder:foo'])

  def test_add_builder_tag_conflict(self):
    with self.assertRaises(errors.InvalidInputError):
      service.add(service.BuildRequest(
          project=self.chromium_project_id,
          bucket='chromium',
          parameters={'builder_name': 'foo'},
          tags=['builder:bar'],
      ))

  def test_add_long_buildset(self):
    with self.assertRaises(errors.InvalidInputError):
      self.add(bucket='b', tags=['buildset:' + ('a' * 2000)])

  def test_buildset_index(self):
    build = self.add(bucket='b', tags=['buildset:foo', 'buildset:bar'])

    for t in build.tags:
      index = model.TagIndex.get_by_id(t)
      self.assertIsNotNone(index)
      self.assertEqual(len(index.entries), 1)
      self.assertEqual(index.entries[0].build_id, build.key.id())
      self.assertEqual(index.entries[0].bucket, 'b')

  def test_buildset_index_with_client_op_id(self):
    build = self.add(
        bucket='b', tags=['buildset:foo'], client_operation_id='0')

    index = model.TagIndex.get_by_id('buildset:foo')
    self.assertIsNotNone(index)
    self.assertEqual(len(index.entries), 1)
    self.assertEqual(index.entries[0].build_id, build.key.id())
    self.assertEqual(index.entries[0].bucket, 'b')

  def test_buildset_index_existing(self):
    model.TagIndex(
        id='buildset:foo',
        entries=[
          model.TagIndexEntry(build_id=int(2**63-1), bucket='b'),
          model.TagIndexEntry(build_id=0, bucket='b'),
        ]).put()
    build = self.add(bucket='b', tags=['buildset:foo'])
    index = model.TagIndex.get_by_id('buildset:foo')
    self.assertIsNotNone(index)
    self.assertEqual(len(index.entries), 3)
    self.assertEqual(index.entries[1].build_id, build.key.id())
    self.assertEqual(index.entries[1].bucket, 'b')

  def test_buildset_index_failed(self):
    with self.assertRaises(errors.InvalidInputError):
      self.add(bucket='', tags=['buildset:foo'])
    index = model.TagIndex.get_by_id('buildset:foo')
    self.assertIsNone(index)

  def test_add_many(self):
    self.mock_cannot(acl.Action.ADD_BUILD, bucket='forbidden')
    results = service.add_many_async([
      service.BuildRequest(
          project=self.chromium_project_id,
          bucket='chromium',
          tags=['buildset:a'],
      ),
      service.BuildRequest(
          project=self.chromium_project_id,
          bucket='chromium',
          tags=['buildset:a'],
      ),
    ]).get_result()
    self.assertEqual(len(results), 2)
    self.assertIsNotNone(results[0][0])
    self.assertIsNone(results[0][1])
    self.assertIsNotNone(results[1][0])
    self.assertIsNone(results[1][1])
    results.sort(key=lambda (b, _): b.key.id())

    index = model.TagIndex.get_by_id('buildset:a')
    self.assertIsNotNone(index)
    self.assertEqual(len(index.entries), 2)
    self.assertEqual(index.entries[0].build_id, results[1][0].key.id())
    self.assertEqual(index.entries[0].bucket, results[1][0].bucket)
    self.assertEqual(index.entries[1].build_id, results[0][0].key.id())
    self.assertEqual(index.entries[1].bucket, results[0][0].bucket)

  def test_add_many_invalid_input(self):
    results = service.add_many_async([
      service.BuildRequest(
          project=self.chromium_project_id,
          bucket='chromium',
          tags=['buildset:a'],
      ),
      service.BuildRequest(
          project=self.chromium_project_id,
          bucket='chromium',
          tags=['buildset:a', 'x'],
      ),
    ]).get_result()
    self.assertEqual(len(results), 2)
    self.assertIsNotNone(results[0][0])
    self.assertIsNone(results[0][1])
    self.assertIsNone(results[1][0])
    self.assertIsNotNone(results[1][1])

    self.assertIsInstance(results[1][1], errors.InvalidInputError)

    index = model.TagIndex.get_by_id('buildset:a')
    self.assertIsNotNone(index)
    self.assertEqual(len(index.entries), 1)
    self.assertEqual(index.entries[0].build_id, results[0][0].key.id())
    self.assertEqual(index.entries[0].bucket, results[0][0].bucket)

  def test_add_many_auth_error(self):
    self.mock_cannot(acl.Action.ADD_BUILD, bucket='forbidden')
    with self.assertRaises(auth.AuthorizationError):
      service.add_many_async([
        service.BuildRequest(
            project=self.chromium_project_id,
            bucket='chromium',
            tags=['buildset:a'],
        ),
        service.BuildRequest(
            project='forbidden',
            bucket='forbidden',
            tags=['buildset:a'],
        ),
      ]).get_result()

    index = model.TagIndex.get_by_id('buildset:a')
    self.assertIsNone(index)

  def test_add_many_with_client_op_id(self):
    req1 = service.BuildRequest(
        project=self.chromium_project_id,
        bucket='chromium',
        tags=['buildset:a'],
        client_operation_id='0',
    )
    req2 = service.BuildRequest(
        project=self.chromium_project_id,
        bucket='chromium',
        tags=['buildset:a'],
    )
    service.add(req1)
    service.add_many_async([req1, req2]).get_result()

    # Build for req1 must be added only once.
    idx = model.TagIndex.get_by_id('buildset:a')
    self.assertEqual(len(idx.entries), 2)
    self.assertEqual(idx.entries[0].bucket, 'chromium')

  def test_add_too_many_to_index(self):
    service.add_many_async([
      service.BuildRequest(
          project=self.chromium_project_id,
          bucket='chromium',
          tags=['buildset:a'],
      )
      for _ in xrange(2000)
    ]).get_result()
    index = model.TagIndex.get_by_id('buildset:a')
    self.assertIsNotNone(index)
    self.assertTrue(index.permanently_incomplete)
    self.assertEqual(len(index.entries), 0)

    # One more for coverage.
    service.add_many_async([
      service.BuildRequest(
          project=self.chromium_project_id,
          bucket='chromium',
          tags=['buildset:a'],
      )
    ]).get_result()

  ################################### RETRY ####################################

  def test_retry(self):
    self.test_build.canary_preference = model.CanaryPreference.CANARY
    self.test_build.initial_tags = ['x:x']
    self.test_build.tags = self.test_build.initial_tags + ['y:y']
    self.test_build.put()
    build = service.retry(self.test_build.key.id())
    self.assertIsNotNone(build)
    self.assertIsNotNone(build.key)
    self.assertNotEqual(build.key.id(), self.test_build.key.id())
    self.assertEqual(build.bucket, self.test_build.bucket)
    self.assertEqual(build.parameters, self.test_build.parameters)
    self.assertEqual(build.retry_of, self.test_build.key.id())
    self.assertEqual(build.tags, ['builder:infra', 'x:x'])
    self.assertEqual(build.canary_preference, model.CanaryPreference.CANARY)

  def test_retry_with_build_address(self):
    self.test_build.put()
    build = service.retry(self.test_build.key.id())
    self.assertIsNotNone(build)
    self.assertIsNotNone(build.key)
    self.assertNotEqual(build.key.id(), self.test_build.key.id())
    self.assertEqual(build.bucket, self.test_build.bucket)
    self.assertEqual(build.parameters, self.test_build.parameters)
    self.assertEqual(build.retry_of, self.test_build.key.id())

  def test_retry_not_found(self):
    with self.assertRaises(errors.BuildNotFoundError):
      service.retry(2)

  #################################### GET #####################################

  def test_get(self):
    self.test_build.put()
    build = service.get(self.test_build.key.id())
    self.assertEqual(build, self.test_build)

  def test_get_nonexistent_build(self):
    self.assertIsNone(service.get(42))

  def test_get_with_auth_error(self):
    self.mock_cannot(acl.Action.VIEW_BUILD)
    self.test_build.put()
    with self.assertRaises(auth.AuthorizationError):
      service.get(self.test_build.key.id())

  ################################### CANCEL ###################################

  def test_cancel(self):
    self.test_build.put()
    build = service.cancel(self.test_build.key.id())
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(build.status_changed_time, utils.utcnow())
    self.assertEqual(build.complete_time, utils.utcnow())
    self.assertEqual(build.result, model.BuildResult.CANCELED)
    self.assertEqual(
      build.cancelation_reason, model.CancelationReason.CANCELED_EXPLICITLY)

  def test_cancel_is_idempotent(self):
    self.test_build.put()
    service.cancel(self.test_build.key.id())
    service.cancel(self.test_build.key.id())

  def test_cancel_started_build(self):
    self.lease()
    self.start()
    service.cancel(self.test_build.key.id())

  def test_cancel_nonexistent_build(self):
    with self.assertRaises(errors.BuildNotFoundError):
      service.cancel(1)

  def test_cancel_with_auth_error(self):
    self.test_build.put()
    self.mock_cannot(acl.Action.CANCEL_BUILD)
    with self.assertRaises(auth.AuthorizationError):
      service.cancel(self.test_build.key.id())

  def test_cancel_completed_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.complete_time = utils.utcnow()
    self.test_build.put()
    with self.assertRaises(errors.BuildIsCompletedError):
      service.cancel(self.test_build.key.id())

  @mock.patch('google.appengine.ext.deferred.defer', autospec=True)
  def test_cancel_swarmbucket_build(self, defer):
    self.test_build.swarming_hostname = 'chromium-swarm.appspot.com'
    self.test_build.swarming_task_id = 'deadbeef'
    self.test_build.put()
    service.cancel(self.test_build.key.id())
    defer.assert_called_with(
        swarming.cancel_task,
        None,
        'chromium-swarm.appspot.com',
        'deadbeef',
        _transactional=True)

  def test_cancel_result_details(self):
    self.test_build.put()
    result_details = {'message': 'bye bye build'}
    build = service.cancel(
        self.test_build.key.id(), result_details=result_details)
    self.assertEqual(build.result_details, result_details)

  #################################### SEARCH ##################################

  def search(self, **query_attrs):
    return service.search(service.SearchQuery(**query_attrs))

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
    self.mock_cannot(acl.Action.SEARCH_BUILDS, 'other bucket')

    build2 = model.Build(bucket='other bucket', tags=[self.INDEXED_TAG])
    self.put_build(self.test_build)
    self.put_build(build2)

    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [self.test_build])
    builds, _ = self.search()
    self.assertEqual(builds, [self.test_build])

    # All buckets are available.
    acl.get_available_buckets.return_value = None
    acl.can_async.side_effect = None
    builds, _ = self.search()
    self.assertEqual(builds, [build2, self.test_build])
    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [build2, self.test_build])

    # No buckets are available.
    acl.get_available_buckets.return_value = []
    self.mock_cannot(acl.Action.SEARCH_BUILDS)
    builds, _ = self.search()
    self.assertEqual(builds, [])
    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [])

  def test_search_with_auth_error(self):
    self.mock_cannot(acl.Action.SEARCH_BUILDS)
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

  @mock.patch('acl.get_available_buckets', autospec=True)
  def test_search_by_build_address(self, get_available_buckets):
    build_address = 'build_address:chromium/infra/1'
    self.test_build.tags = [build_address]
    self.put_build(self.test_build)

    get_available_buckets.return_value = [self.test_build.bucket]
    builds, _ = self.search(tags=[build_address])
    self.assertEqual(builds, [self.test_build])

  def test_search_bucket(self):
    self.put_build(self.test_build)
    build2 = model.Build(
        bucket='other bucket',
    )
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
        buckets=[self.test_build.bucket],
        status=service.StatusFilter.SCHEDULED)
    self.assertEqual(builds, [self.test_build])
    builds, _ = self.search(
        buckets=[self.test_build.bucket],
        status=service.StatusFilter.SCHEDULED,
        tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [self.test_build])

    builds, _ = self.search(
        buckets=[self.test_build.bucket],
        status=service.StatusFilter.COMPLETED,
        result=model.BuildResult.FAILURE,
        tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [])
    builds, _ = self.search(
        buckets=[self.test_build.bucket],
        status=service.StatusFilter.COMPLETED,
        result=model.BuildResult.FAILURE)
    self.assertEqual(builds, [])

    builds, _ = self.search(
        buckets=[self.test_build.bucket],
        status=service.StatusFilter.INCOMPLETE)
    self.assertEqual(builds, [self.test_build])
    builds, _ = self.search(
        buckets=[self.test_build.bucket],
        status=service.StatusFilter.INCOMPLETE,
        tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [self.test_build])

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

  def test_search_by_creation_time_range(self):
    too_old = model.BEGINING_OF_THE_WORLD - datetime.timedelta(milliseconds=1)
    old_time = model.BEGINING_OF_THE_WORLD + datetime.timedelta(milliseconds=1)
    new_time = datetime.datetime(2012, 12, 5)

    create_time = datetime.datetime(2011, 2, 4)
    old_build = model.Build(
        id=model.create_build_id(create_time),
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
            self.test_build.create_time + datetime.timedelta(milliseconds=1)),
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
    self.mock_cannot(acl.Action.SEARCH_BUILDS, bucket=self.test_build.bucket)
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
        start_cursor=next_cursor)
    self.assertEqual(len(second_page), 10)
    # no cover due to a bug in coverage (http://stackoverflow.com/a/35325514)
    self.assertTrue(
        any(new not in first_page for new in second_page))  # pragma: no cover

  def test_search_with_paging_using_tag_index(self):
    self.put_many_builds(20, tags=[self.INDEXED_TAG])

    first_page, first_cursor = self.search(
        tags=[self.INDEXED_TAG],
        max_builds=10,
    )
    self.assertEqual(len(first_page), 10)
    self.assertEqual(first_cursor, 'id>%d' % first_page[-1].key.id())

    second_page, second_cursor = self.search(
        tags=[self.INDEXED_TAG],
        max_builds=10,
        start_cursor=first_cursor)
    self.assertEqual(len(second_page), 10)

    third_page, third_cursor = self.search(
        tags=[self.INDEXED_TAG],
        max_builds=10,
        start_cursor=second_cursor)
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

    self.mock_cannot(acl.Action.SEARCH_BUILDS, 'secret.bucket')
    builds, _ = self.search(
        tags=[self.INDEXED_TAG], buckets=[self.test_build.bucket])
    self.assertEqual(builds, [self.test_build])

  def test_search_with_invalid_tag_entry_order(self):
    self.test_build.tags = [self.INDEXED_TAG]
    self.test_build.put()

    model.TagIndex(
        id=self.INDEXED_TAG,
        entries=[
          model.TagIndexEntry(
              bucket=self.test_build.bucket,
              build_id=1,
          ),
          model.TagIndexEntry(
              bucket=self.test_build.bucket,
              build_id=2,
          ),
        ]
    ).put()

    builds, _ = self.search(
        buckets=[self.test_build.bucket], tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [self.test_build])

    with self.assertRaises(errors.InvalidIndexEntryOrder):
      self.search(
          buckets=[self.test_build.bucket], tags=[self.INDEXED_TAG],
          start_cursor='id>0')

  def test_search_with_dup_tag_entries(self):
    self.test_build.tags = [self.INDEXED_TAG]
    self.test_build.put()

    entry = model.TagIndexEntry(
        bucket=self.test_build.bucket,
        build_id=self.test_build.key.id(),
    )
    model.TagIndex(
        id=self.INDEXED_TAG,
        entries=[entry, entry],
    ).put()

    builds, _ = self.search(
        buckets=[self.test_build.bucket], tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [self.test_build])

  def test_search_with_incomplete_index(self):
    self.test_build.tags = [self.INDEXED_TAG]
    self.test_build.put()

    model.TagIndex(
        id=self.INDEXED_TAG,
        permanently_incomplete=True).put()

    builds, _ = self.search(
        buckets=[self.test_build.bucket], tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [self.test_build])

    with self.assertRaises(errors.TagIndexIncomplete):
      self.search(
          buckets=[self.test_build.bucket], tags=[self.INDEXED_TAG],
          start_cursor='id>0')

  def test_search_with_no_tag_index(self):
    builds, _ = self.search()
    self.assertEqual(builds, [])

  def test_search_with_inconsistent_entries(self):
    self.put_build(self.test_build)

    will_be_deleted = model.Build(
        bucket=self.test_build.bucket, tags=[self.INDEXED_TAG])
    self.put_build(will_be_deleted)  # updates index
    will_be_deleted.key.delete()

    buildset_will_change = model.Build(
        bucket=self.test_build.bucket, tags=[self.INDEXED_TAG])
    self.put_build(buildset_will_change)  # updates index
    buildset_will_change.tags = []
    buildset_will_change.put()

    builds, _ = self.search(tags=[self.INDEXED_TAG])
    self.assertEqual(builds, [self.test_build])

  def test_search_with_tag_index_cursor(self):
    builds = self.put_many_builds(10)
    builds.reverse()
    res, cursor = self.search(
        tags=[self.INDEXED_TAG],
        start_cursor='id>%d' % builds[-1].key.id())
    self.assertEqual(res, [])
    self.assertIsNone(cursor)

    builds = self.put_many_builds(10, tags=[self.INDEXED_TAG])
    builds.reverse()
    res, cursor = self.search(
        tags=[self.INDEXED_TAG],
        buckets=[self.test_build.bucket],
        create_time_low=builds[5].create_time,
        start_cursor='id>%d' % builds[7].key.id())
    self.assertEqual(res, [])
    self.assertIsNone(cursor)

    res, cursor = self.search(
        tags=[self.INDEXED_TAG],
        buckets=[self.test_build.bucket],
        create_time_high=builds[7].create_time,
        start_cursor='id>%d' % builds[5].key.id())
    # create_time_high is exclusive
    self.assertEqual(res, builds[8:])
    self.assertIsNone(cursor)

  def test_search_with_tag_index_cursor_but_no_inded_tag(self):
    with self.assertRaises(errors.InvalidInputError):
      self.search(start_cursor='id>1')

  #################################### PEEK ####################################

  def test_peek(self):
    self.test_build.put()
    builds, _ = service.peek(buckets=[self.test_build.bucket])
    self.assertEqual(builds, [self.test_build])

  def test_peek_multi(self):
    self.test_build.key = ndb.Key(model.Build, 10)
    self.test_build.put()
    # We test that peek returns builds in decreasing order of the build key. The
    # build key is derived from the inverted current time, so later builds get
    # smaller ids. Only exception: if the time is the same, randomness decides
    # the order. So artificially create an id here to avoid flakiness.
    build2 = model.Build(id=self.test_build.key.id() - 1, bucket='bucket2')
    build2.put()
    builds, _ = service.peek(buckets=[self.test_build.bucket, 'bucket2'])
    self.assertEqual(builds, [self.test_build, build2])

  def test_peek_with_paging(self):
    self.put_many_builds()
    first_page, next_cursor = service.peek(
      buckets=[self.test_build.bucket])
    self.assertTrue(first_page)
    self.assertTrue(next_cursor)

    second_page, _ = service.peek(
      buckets=[self.test_build.bucket], start_cursor=next_cursor)

    self.assertTrue(all(b not in second_page for b in first_page))

  def test_peek_with_bad_cursor(self):
    self.put_many_builds()
    with self.assertRaises(errors.InvalidInputError):
      service.peek(buckets=[self.test_build.bucket], start_cursor='abc')

  def test_peek_without_buckets(self):
    with self.assertRaises(errors.InvalidInputError):
      service.peek(buckets=[])

  def test_peek_with_auth_error(self):
    self.mock_cannot(acl.Action.SEARCH_BUILDS)
    self.test_build.put()
    with self.assertRaises(auth.AuthorizationError):
      service.peek(buckets=[self.test_build.bucket])

  def test_peek_does_not_return_leased_builds(self):
    self.test_build.put()
    self.lease()
    builds, _ = service.peek([self.test_build.bucket])
    self.assertFalse(builds)

  def test_peek_200_builds(self):
    for _ in xrange(200):
      model.Build(bucket=self.test_build.bucket).put()
    builds, _ = service.peek([self.test_build.bucket], max_builds=200)
    self.assertTrue(len(builds) <= 100)

  #################################### LEASE ###################################

  def lease(self, lease_expiration_date=None):
    if not (self.test_build.key and self.test_build.key.get()):
      self.test_build.put()
    success, self.test_build = service.lease(
      self.test_build.key.id(),
      lease_expiration_date=lease_expiration_date,
    )
    return success

  def test_lease(self):
    expiration_date = utils.utcnow() + datetime.timedelta(minutes=1)
    self.assertTrue(self.lease(lease_expiration_date=expiration_date))
    self.assertTrue(self.test_build.is_leased)
    self.assertGreater(self.test_build.lease_expiration_date, utils.utcnow())
    self.assertEqual(self.test_build.leasee, self.current_identity)

  def test_lease_build_with_auth_error(self):
    self.mock_cannot(acl.Action.LEASE_BUILD)
    build = self.test_build
    build.put()
    with self.assertRaises(auth.AuthorizationError):
      self.lease()

  def test_cannot_lease_a_leased_build(self):
    build = self.test_build
    build.put()
    self.assertTrue(self.lease())
    self.assertFalse(self.lease())

  def test_cannot_lease_a_nonexistent_build(self):
    with self.assertRaises(errors.BuildNotFoundError):
      service.lease(build_id=42)

  def test_cannot_lease_for_whole_day(self):
    with self.assertRaises(errors.InvalidInputError):
      self.lease(
        lease_expiration_date=utils.utcnow() + datetime.timedelta(days=1))

  def test_cannot_set_expiration_date_to_past(self):
    with self.assertRaises(errors.InvalidInputError):
      yesterday = utils.utcnow() - datetime.timedelta(days=1)
      self.lease(lease_expiration_date=yesterday)

  def test_cannot_lease_with_non_datetime_expiration_date(self):
    with self.assertRaises(errors.InvalidInputError):
      self.lease(lease_expiration_date=1)

  def test_leasing_regenerates_lease_key(self):
    orig_lease_key = 42
    self.lease()
    self.assertNotEqual(self.test_build.lease_key, orig_lease_key)

  def test_cannot_lease_completed_build(self):
    build = self.test_build
    build.status = model.BuildStatus.COMPLETED
    build.result = model.BuildResult.SUCCESS
    build.complete_time = utils.utcnow()
    build.put()
    self.assertFalse(self.lease())

  ################################### UNELASE ##################################

  def test_reset(self):
    self.lease()
    build = service.reset(self.test_build.key.id())
    self.assertEqual(build.status, model.BuildStatus.SCHEDULED)
    self.assertEqual(build.status_changed_time, utils.utcnow())
    self.assertIsNone(build.lease_key)
    self.assertIsNone(build.lease_expiration_date)
    self.assertIsNone(build.leasee)
    self.assertIsNone(build.canary)
    self.assertTrue(self.lease())

  def test_reset_is_idempotent(self):
    self.lease()
    build_id = self.test_build.key.id()
    service.reset(build_id)
    service.reset(build_id)

  def test_reset_completed_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.complete_time = utils.utcnow()
    self.test_build.put()

    with self.assertRaises(errors.BuildIsCompletedError):
      service.reset(self.test_build.key.id())

  def test_cannot_reset_nonexistent_build(self):
    with self.assertRaises(errors.BuildNotFoundError):
      service.reset(123)

  def test_reset_with_auth_error(self):
    self.lease()
    self.mock_cannot(acl.Action.RESET_BUILD)
    with self.assertRaises(auth.AuthorizationError):
      service.reset(self.test_build.key.id())

  #################################### START ###################################

  def test_validate_malformed_url(self):
    with self.assertRaises(errors.InvalidInputError):
      service.validate_url('svn://sdfsf')

  def test_validate_relative_url(self):
    with self.assertRaises(errors.InvalidInputError):
      service.validate_url('sdfsf')

  def test_validate_nonstring_url(self):
    with self.assertRaises(errors.InvalidInputError):
      service.validate_url(123)

  def start(self, url=None, lease_key=None, canary=False):
    self.test_build = service.start(
      self.test_build.key.id(),
      lease_key or self.test_build.lease_key,
      url, canary)

  def test_start(self):
    self.lease()
    self.start(url='http://localhost', canary=True)
    self.assertEqual(self.test_build.status, model.BuildStatus.STARTED)
    self.assertEqual(self.test_build.url, 'http://localhost')
    self.assertEqual(self.test_build.start_time, self.now)
    self.assertTrue(self.test_build.canary)

  def test_start_started_build(self):
    self.lease()
    build_id = self.test_build.key.id()
    lease_key = self.test_build.lease_key
    url = 'http://localhost/'

    service.start(build_id, lease_key, url, False)
    service.start(build_id, lease_key, url, False)
    service.start(build_id, lease_key, url + '1', False)

  def test_start_non_leased_build(self):
    self.test_build.put()
    with self.assertRaises(errors.LeaseExpiredError):
      service.start(self.test_build.key.id(), 42, None, False)

  def test_start_completed_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.complete_time = utils.utcnow()
    self.test_build.put()
    with self.assertRaises(errors.BuildIsCompletedError):
      service.start(self.test_build.key.id(), 42, None, False)

  def test_start_without_lease_key(self):
    with self.assertRaises(errors.InvalidInputError):
      service.start(1, None, None, False)

  @contextlib.contextmanager
  def callback_test(self):
    self.test_build.key = ndb.Key(model.Build, 1)
    self.test_build.pubsub_callback = model.PubSubCallback(
        topic='projects/example/topics/buildbucket',
        user_data='hello',
        auth_token='secret',
    )
    self.test_build.put()
    yield
    events.enqueue_tasks_async.assert_called_with('backend-default', [
      {
        'url': '/internal/task/buildbucket/notify/1',
        'payload': json.dumps({
          'id': 1,
          'mode': 'global',
        }, sort_keys=True),
        'age_limit_sec': model.BUILD_TIMEOUT.total_seconds(),
      },
      {
        'url': '/internal/task/buildbucket/notify/1',
        'payload': json.dumps({
          'id': 1,
          'mode': 'callback',
        }, sort_keys=True),
        'age_limit_sec': model.BUILD_TIMEOUT.total_seconds(),
      },
    ])

  def test_start_creates_notification_task(self):
    self.lease()
    with self.callback_test():
      self.start()

  ################################## HEARTBEAT #################################

  def test_heartbeat(self):
    self.lease()
    new_expiration_date = utils.utcnow() + datetime.timedelta(minutes=1)
    build = service.heartbeat(
      self.test_build.key.id(), self.test_build.lease_key,
      lease_expiration_date=new_expiration_date)
    self.assertEqual(build.lease_expiration_date, new_expiration_date)

  def test_heartbeat_completed(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.CANCELED
    self.test_build.cancelation_reason = (
      model.CancelationReason.CANCELED_EXPLICITLY)
    self.test_build.complete_time = utils.utcnow()
    self.test_build.put()

    new_expiration_date = utils.utcnow() + datetime.timedelta(minutes=1)
    with self.assertRaises(errors.BuildIsCompletedError):
      service.heartbeat(
        self.test_build.key.id(), 0,
        lease_expiration_date=new_expiration_date)

  def test_heartbeat_batch(self):
    self.lease()
    new_expiration_date = utils.utcnow() + datetime.timedelta(minutes=1)
    results = service.heartbeat_batch(
      [
        {
          'build_id': self.test_build.key.id(),
          'lease_key': self.test_build.lease_key,
          'lease_expiration_date': new_expiration_date
        },
        {
          'build_id': 42,
          'lease_key': 42,
          'lease_expiration_date': new_expiration_date,
        },
      ])

    self.assertEqual(len(results), 2)

    self.test_build = self.test_build.key.get()
    self.assertEqual(
      results[0],
      (self.test_build.key.id(), self.test_build, None))

    self.assertIsNone(results[1][1])
    self.assertTrue(isinstance(results[1][2], errors.BuildNotFoundError))

  def test_heartbeat_without_expiration_date(self):
    self.lease()
    with self.assertRaises(errors.InvalidInputError):
      service.heartbeat(
        self.test_build.key.id(), self.test_build.lease_key,
        lease_expiration_date=None)

  ################################### COMPLETE #################################

  def succeed(self, **kwargs):
    self.test_build = service.succeed(
      self.test_build.key.id(), self.test_build.lease_key, **kwargs)

  def test_succeed(self):
    self.lease()
    self.start()
    self.succeed()
    self.assertEqual(self.test_build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(self.test_build.status_changed_time, utils.utcnow())
    self.assertEqual(self.test_build.result, model.BuildResult.SUCCESS)
    self.assertIsNotNone(self.test_build.complete_time)

  def test_succeed_timed_out_build(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.CANCELED
    self.test_build.cancelation_reason = model.CancelationReason.TIMEOUT
    self.test_build.complete_time = utils.utcnow()
    self.test_build.put()
    with self.assertRaises(errors.BuildIsCompletedError):
      service.succeed(self.test_build.key.id(), 42)

  def test_succeed_is_idempotent(self):
    self.lease()
    self.start()
    build_id = self.test_build.key.id()
    lease_key = self.test_build.lease_key
    service.succeed(build_id, lease_key)
    service.succeed(build_id, lease_key)

  def test_succeed_with_new_tags(self):
    self.test_build.tags = ['a:1']
    self.test_build.put()
    self.lease()
    self.start()
    self.succeed(new_tags=['b:2'])
    self.assertEqual(self.test_build.tags, ['a:1', 'b:2'])

  def test_fail(self):
    self.lease()
    self.start()
    self.test_build = service.fail(
      self.test_build.key.id(), self.test_build.lease_key)
    self.assertEqual(self.test_build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(self.test_build.status_changed_time, utils.utcnow())
    self.assertEqual(self.test_build.result, model.BuildResult.FAILURE)
    self.assertIsNotNone(self.test_build.complete_time)

  def test_fail_with_details(self):
    self.lease()
    self.start()
    result_details = {'transient_failure': True}
    self.test_build = service.fail(
      self.test_build.key.id(), self.test_build.lease_key,
      result_details=result_details)
    self.assertEqual(self.test_build.result_details, result_details)

  def test_complete_with_url(self):
    self.lease()
    self.start()
    url = 'http://localhost/1'
    self.succeed(url=url)
    self.assertEqual(self.test_build.url, url)

  def test_complete_not_started_build(self):
    self.lease()
    self.succeed()

  def test_completion_creates_notification_task(self):
    self.lease()
    self.start()
    with self.callback_test():
      self.succeed()

  ########################## RESET EXPIRED BUILDS ##############################

  def test_reschedule_expired_builds(self):
    self.test_build.lease_expiration_date = utils.utcnow()
    self.test_build.lease_key = 1
    self.test_build.leasee = self.current_identity
    self.test_build.put()

    service.reset_expired_builds()
    build = self.test_build.key.get()
    self.assertEqual(build.status, model.BuildStatus.SCHEDULED)
    self.assertIsNone(build.lease_key)

  def test_completed_builds_are_not_reset(self):
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.complete_time = utils.utcnow()
    self.test_build.put()
    service.reset_expired_builds()
    build = self.test_build.key.get()
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)

  def test_build_timeout(self):
    self.test_build.create_time = utils.utcnow() - datetime.timedelta(days=365)
    self.test_build.put()

    service.reset_expired_builds()
    build = self.test_build.key.get()
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(build.result, model.BuildResult.CANCELED)
    self.assertEqual(build.cancelation_reason, model.CancelationReason.TIMEOUT)
    self.assertIsNone(build.lease_key)

  ########################## RESET EXPIRED BUILDS ##############################

  def test_delete_many_scheduled_builds(self):
    self.test_build.put()
    completed_build = model.Build(
        bucket=self.test_build.bucket,
        status=model.BuildStatus.COMPLETED,
        result=model.BuildResult.SUCCESS,
        create_time=utils.utcnow(),
        complete_time=utils.utcnow() + datetime.timedelta(seconds=1),
        canary=False,
    )
    completed_build.put()
    self.assertIsNotNone(self.test_build.key.get())
    self.assertIsNotNone(completed_build.key.get())
    service._task_delete_many_builds(
        self.test_build.bucket, model.BuildStatus.SCHEDULED)
    self.assertIsNone(self.test_build.key.get())
    self.assertIsNotNone(completed_build.key.get())

  def test_delete_many_started_builds(self):
    self.test_build.put()

    started_build = model.Build(
        bucket=self.test_build.bucket,
        status=model.BuildStatus.STARTED,
        create_time=utils.utcnow(),
        start_time=utils.utcnow(),
        canary=False,
    )
    started_build.put()

    completed_build = model.Build(
        bucket=self.test_build.bucket,
        status=model.BuildStatus.COMPLETED,
        result=model.BuildResult.SUCCESS,
        create_time=utils.utcnow(),
        complete_time=utils.utcnow(),
        canary=False,
    )
    completed_build.put()

    service._task_delete_many_builds(
        self.test_build.bucket, model.BuildStatus.STARTED)
    self.assertIsNotNone(self.test_build.key.get())
    self.assertIsNone(started_build.key.get())
    self.assertIsNotNone(completed_build.key.get())

  def test_delete_many_builds_with_tags(self):
    self.test_build.tags = ['tag:1']
    self.test_build.put()

    service._task_delete_many_builds(
        self.test_build.bucket, model.BuildStatus.SCHEDULED, tags=['tag:0'])
    self.assertIsNotNone(self.test_build.key.get())

    service._task_delete_many_builds(
        self.test_build.bucket, model.BuildStatus.SCHEDULED, tags=['tag:1'])
    self.assertIsNone(self.test_build.key.get())

  def test_delete_many_builds_created_by(self):
    self.test_build.created_by = auth.Identity('user', 'nodir@google.com')
    self.test_build.put()
    other_build = model.Build(bucket=self.test_build.bucket)
    other_build.put()

    service._task_delete_many_builds(
        self.test_build.bucket, model.BuildStatus.SCHEDULED,
        created_by='nodir@google.com')
    self.assertIsNone(self.test_build.key.get())
    self.assertIsNotNone(other_build.key.get())

  def test_delete_many_builds_auth_error(self):
    self.mock_cannot(acl.Action.DELETE_SCHEDULED_BUILDS)
    with self.assertRaises(auth.AuthorizationError):
      service.delete_many_builds(
          self.test_build.bucket, model.BuildStatus.SCHEDULED)

  def test_delete_many_builds_schedule_task(self):
    service.delete_many_builds(
        self.test_build.bucket, model.BuildStatus.SCHEDULED)

  def test_delete_many_completed_builds(self):
    with self.assertRaises(errors.InvalidInputError):
      service.delete_many_builds(
          self.test_build.bucket, model.BuildStatus.COMPLETED)

  ###########################  LONGEST_PENDING_TIME ############################

  def test_pause_bucket(self):
    self.test_build.bucket = 'foo'
    self.put_many_builds(5)

    self.test_build.bucket = 'bar'
    self.put_many_builds(5)

    service.pause('foo', True)
    builds, _ = service.peek(['foo','bar'])
    self.assertEqual(len(builds), 5)
    self.assertFalse(any(b.bucket == 'foo' for b in builds))

  def test_pause_all_requested_buckets(self):
    self.test_build.bucket = 'foo'
    self.put_many_builds(5)

    service.pause('foo', True)
    builds, _ = service.peek(['foo'])
    self.assertEqual(len(builds), 0)

  def test_pause_then_unpause(self):
    self.test_build.bucket = 'foo'
    self.test_build.put()

    service.pause('foo', True)
    service.pause('foo', True)  # Again, to cover equality case.
    builds, _ = service.peek(['foo'])
    self.assertEqual(len(builds), 0)

    service.pause('foo', False)
    builds, _ = service.peek(['foo'])
    self.assertEqual(len(builds), 1)

  def test_pause_bucket_invalid_bucket_name(self):
    with self.assertRaises(errors.InvalidInputError):
      service.pause('wharbl|gharbl', True)

  def test_pause_bucket_auth_error(self):
    self.mock_cannot(acl.Action.PAUSE_BUCKET)
    with self.assertRaises(auth.AuthorizationError):
      service.pause('test', True)

  def test_pause_invalid_bucket(self):
    config.get_bucket_async.return_value = future((None, None))
    with self.assertRaises(errors.InvalidInputError):
      service.pause('test', True)

  def test_pause_swarming_bucket(self):
    self.chromium_bucket.swarming.MergeFrom(self.chromium_swarming)
    with self.assertRaises(errors.InvalidInputError):
      service.pause('test', True)


  ###########################  LONGEST_PENDING_TIME ############################

  def test_longest_pending_time(self):
    builds = [
      model.Build(
          bucket='chromium',
          tags=['builder:x'],
          create_time=self.now - datetime.timedelta(minutes=10),
      ),
      model.Build(
          bucket='chromium',
          tags=['builder:x'],
          create_time=self.now - datetime.timedelta(minutes=20),
      ),
      model.Build(
          bucket='chromium',
          tags=['builder:y'],
          create_time=self.now - datetime.timedelta(minutes=30),
      ),
    ]
    for b in builds:
      b.put()
    actual = service.longest_pending_time('chromium', 'x')
    self.assertEqual(actual, datetime.timedelta(minutes=20))

  def test_longest_pending_time_invalid_input(self):
    with self.assertRaises(errors.InvalidInputError):
      service.longest_pending_time('', 'x')
    with self.assertRaises(errors.InvalidInputError):
      service.longest_pending_time('chromium', '')

  def test_longest_pending_time_no_builds(self):
    actual = service.longest_pending_time('chromium', 'x')
    self.assertEqual(actual, datetime.timedelta(0))

  def test_longest_pending_time_without_permissions(self):
    self.mock_cannot(acl.Action.ACCESS_BUCKET)
    with self.assertRaises(auth.AuthorizationError):
      service.longest_pending_time('chromium', 'x')
