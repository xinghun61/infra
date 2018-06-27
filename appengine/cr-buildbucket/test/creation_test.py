# Copyright 2018 The Chromium Authors. All rights reserved.
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

from proto import common_pb2
from proto.config import project_config_pb2
from proto.config import service_config_pb2
from test.test_util import future, future_exception
import api_common
import config
import creation
import errors
import model
import notifications
import search
import swarming
import user
import v2


class CreationTest(testing.AppengineTestCase):
  test_build = None

  def setUp(self):
    super(CreationTest, self).setUp()
    user.clear_request_cache()

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
    self.chromium_swarming = project_config_pb2.Swarming(
        hostname='chromium-swarm.appspot.com',
        builders=[
            project_config_pb2.Builder(
                name='infra',
                dimensions=['pool:default'],
                build_numbers=project_config_pb2.YES,
                recipe=project_config_pb2.Builder.Recipe(
                    repository='https://example.com',
                    name='presubmit',
                ),
            ),
        ],
    )
    self.patch(
        'config.get_bucket_async',
        return_value=future(('project', self.chromium_bucket))
    )
    self.patch('swarming.create_task_async', return_value=future(None))
    self.patch('swarming.cancel_task_async', return_value=future(None))

    self.test_build = model.Build(
        id=model.create_build_ids(self.now, 1)[0],
        bucket='chromium',
        project=self.chromium_project_id,
        create_time=self.now,
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

    self.patch(
        'google.appengine.api.app_identity.get_default_version_hostname',
        autospec=True,
        return_value='buildbucket.example.com'
    )

    self.patch(
        'notifications.enqueue_tasks_async',
        autospec=True,
        return_value=future(None)
    )
    self.patch(
        'config.get_settings_async',
        autospec=True,
        return_value=future(service_config_pb2.SettingsCfg())
    )

    self.patch('creation._should_update_builder', side_effect=lambda p: p > 0.5)

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

  def add(self, bucket, **request_fields):
    build_req = creation.BuildRequest(
        self.chromium_project_id, bucket, **request_fields
    )
    return creation.add_async(build_req).get_result()

  def test_add(self):
    params = {model.BUILDER_PARAMETER: 'linux_rel'}
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

  def test_add_update_builders(self):
    recently = self.now - datetime.timedelta(minutes=1)
    while_ago = self.now - datetime.timedelta(minutes=61)
    ndb.put_multi([
        model.Builder(id='chromium:try:linux_rel', last_scheduled=recently),
        model.Builder(id='chromium:try:mac_rel', last_scheduled=while_ago),
    ])

    creation.add_many_async([
        creation.BuildRequest(
            project='chromium',
            bucket='try',
            parameters={model.BUILDER_PARAMETER: 'linux_rel'},
            canary_preference=model.CanaryPreference.PROD,
        ),
        creation.BuildRequest(
            project='chromium',
            bucket='try',
            parameters={model.BUILDER_PARAMETER: 'mac_rel'},
            canary_preference=model.CanaryPreference.PROD,
        ),
        creation.BuildRequest(
            project='chromium',
            bucket='try',
            parameters={model.BUILDER_PARAMETER: 'win_rel'},
            canary_preference=model.CanaryPreference.PROD,
        ),
    ]).get_result()

    builders = model.Builder.query().fetch()
    self.assertEqual(len(builders), 3)
    self.assertEqual(builders[0].key.id(), 'chromium:try:linux_rel')
    self.assertEqual(builders[0].last_scheduled, recently)
    self.assertEqual(builders[1].key.id(), 'chromium:try:mac_rel')
    self.assertEqual(builders[1].last_scheduled, self.now)
    self.assertEqual(builders[2].key.id(), 'chromium:try:win_rel')
    self.assertEqual(builders[2].last_scheduled, self.now)

  def test_add_with_client_operation_id(self):
    build = self.add(
        bucket='chromium',
        parameters={model.BUILDER_PARAMETER: 'linux_rel'},
        client_operation_id='1',
    )
    build2 = self.add(
        bucket='chromium',
        parameters={model.BUILDER_PARAMETER: 'linux_rel'},
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
    self.mock_cannot(user.Action.ADD_BUILD)
    with self.assertRaises(auth.AuthorizationError):
      self.add(bucket=self.test_build.bucket)

  def test_add_with_bad_parameters(self):
    with self.assertRaises(errors.InvalidInputError):
      self.add(bucket='bucket', parameters=[])

  def test_add_with_swarming_400(self):
    self.chromium_bucket.swarming.MergeFrom(self.chromium_swarming)
    swarming.create_task_async.return_value = future_exception(
        net.Error('', status_code=400, response='bad request')
    )
    with self.assertRaises(errors.InvalidInputError):
      self.add(bucket=self.test_build.bucket)

  def test_add_with_build_numbers(self):
    self.chromium_bucket.swarming.MergeFrom(self.chromium_swarming)

    build_numbers = {}

    def create_task_async(build, build_number):
      build_numbers[build.parameters['i']] = build_number
      return future(None)

    swarming.create_task_async.side_effect = create_task_async

    (_, ex0), (_, ex1) = creation.add_many_async([
        creation.BuildRequest(
            project=self.chromium_project_id,
            bucket=self.chromium_bucket.name,
            parameters={model.BUILDER_PARAMETER: 'infra', 'i': 1},
        ),
        creation.BuildRequest(
            project=self.chromium_project_id,
            bucket=self.chromium_bucket.name,
            parameters={model.BUILDER_PARAMETER: 'infra', 'i': 2},
        )
    ]).get_result()

    self.assertIsNone(ex0)
    self.assertIsNone(ex1)
    self.assertEqual(build_numbers, {1: 1, 2: 2})

  @mock.patch('sequence.try_return_async', autospec=True)
  def test_add_with_build_numbers_and_return(self, try_return_async):
    try_return_async.return_value = future(None)
    self.chromium_bucket.swarming.MergeFrom(self.chromium_swarming)

    class Error(Exception):
      pass

    swarming.create_task_async.return_value = future_exception(Error())

    with self.assertRaises(Error):
      creation.add_async(
          creation.BuildRequest(
              project=self.chromium_project_id,
              bucket=self.chromium_bucket.name,
              parameters={model.BUILDER_PARAMETER: 'infra'},
          )
      ).get_result()

    try_return_async.assert_called_with('chromium/infra', 1)

  def test_add_with_swarming_200_and_400(self):
    self.chromium_bucket.swarming.MergeFrom(self.chromium_swarming)

    def create_task_async(b, number):  # pylint: disable=unused-argument
      if b.parameters['i'] == 1:
        return future_exception(
            net.Error('', status_code=400, response='bad request')
        )
      b.swarming_hostname = self.chromium_bucket.swarming.hostname
      b.swarming_task_id = 'deadbeef'
      return future(None)

    swarming.create_task_async.side_effect = create_task_async

    (b0, ex0), (b1, ex1) = creation.add_many_async([
        creation.BuildRequest(
            project=self.chromium_project_id,
            bucket=self.chromium_bucket.name,
            parameters={model.BUILDER_PARAMETER: 'infra', 'i': 0},
        ),
        creation.BuildRequest(
            project=self.chromium_project_id,
            bucket=self.chromium_bucket.name,
            parameters={model.BUILDER_PARAMETER: 'infra', 'i': 1},
        )
    ]).get_result()

    self.assertIsNone(ex0)
    self.assertEqual(b0.bucket, self.chromium_bucket.name)

    self.assertIsNotNone(ex1)
    self.assertIsNone(b1)

  def test_add_with_swarming_403(self):
    self.chromium_bucket.swarming.MergeFrom(self.chromium_swarming)

    swarming.create_task_async.return_value = future_exception(
        net.AuthError('', status_code=403, response='no no')
    )
    with self.assertRaisesRegexp(auth.AuthorizationError, 'no no'):
      self.add(bucket=self.test_build.bucket)

  def test_add_with_builder_name(self):
    build = self.add(
        bucket='chromium',
        parameters={model.BUILDER_PARAMETER: 'linux_rel'},
        client_operation_id='1',
    )
    self.assertTrue('builder:linux_rel' in build.tags)

  def test_add_builder_tag(self):
    build = self.add(
        bucket='chromium',
        parameters={model.BUILDER_PARAMETER: 'foo'},
    )
    self.assertEqual(build.tags, ['builder:foo'])

  def test_add_builder_tag_multi(self):
    build = self.add(
        bucket='chromium',
        parameters={model.BUILDER_PARAMETER: 'foo'},
        tags=['builder:foo', 'builder:foo'],
    )
    self.assertEqual(build.tags, ['builder:foo'])

  def test_add_builder_tag_different(self):
    with self.assertRaises(errors.InvalidInputError):
      self.add(
          bucket='chromium',
          tags=['builder:foo', 'builder:bar'],
      )

  def test_add_builder_tag_coincide(self):
    build = self.add(
        bucket='chromium',
        parameters={model.BUILDER_PARAMETER: 'foo'},
        tags=['builder:foo'],
    )
    self.assertEqual(build.tags, ['builder:foo'])

  def test_add_builder_tag_conflict(self):
    with self.assertRaises(errors.InvalidInputError):
      self.add(
          bucket='chromium',
          parameters={model.BUILDER_PARAMETER: 'foo'},
          tags=['builder:bar'],
      )

  def test_add_long_buildset(self):
    with self.assertRaises(errors.InvalidInputError):
      self.add(bucket='b', tags=['buildset:' + ('a' * 2000)])

  def test_buildset_index(self):
    build = self.add(bucket='b', tags=['buildset:foo', 'buildset:bar'])

    for t in build.tags:
      index = search.TagIndex.get_by_id(t)
      self.assertIsNotNone(index)
      self.assertEqual(len(index.entries), 1)
      self.assertEqual(index.entries[0].build_id, build.key.id())
      self.assertEqual(index.entries[0].bucket, 'b')

  def test_buildset_index_with_client_op_id(self):
    build = self.add(bucket='b', tags=['buildset:foo'], client_operation_id='0')

    index = search.TagIndex.get_by_id('buildset:foo')
    self.assertIsNotNone(index)
    self.assertEqual(len(index.entries), 1)
    self.assertEqual(index.entries[0].build_id, build.key.id())
    self.assertEqual(index.entries[0].bucket, 'b')

  def test_buildset_index_existing(self):
    search.TagIndex(
        id='buildset:foo',
        entries=[
            search.TagIndexEntry(build_id=int(2**63 - 1), bucket='b'),
            search.TagIndexEntry(build_id=0, bucket='b'),
        ]
    ).put()
    build = self.add(bucket='b', tags=['buildset:foo'])
    index = search.TagIndex.get_by_id('buildset:foo')
    self.assertIsNotNone(index)
    self.assertEqual(len(index.entries), 3)
    self.assertIn(build.key.id(), [e.build_id for e in index.entries])
    self.assertIn('b', [e.bucket for e in index.entries])

  def test_buildset_index_failed(self):
    with self.assertRaises(errors.InvalidInputError):
      self.add(bucket='', tags=['buildset:foo'])
    index = search.TagIndex.get_by_id('buildset:foo')
    self.assertIsNone(index)

  def test_add_many(self):
    self.mock_cannot(user.Action.ADD_BUILD, bucket='forbidden')
    results = creation.add_many_async([
        creation.BuildRequest(
            project=self.chromium_project_id,
            bucket='chromium',
            tags=['buildset:a'],
        ),
        creation.BuildRequest(
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

    self.assertEqual(
        results, sorted(results, key=lambda (b, _): b.key.id(), reverse=True)
    )
    results.reverse()

    index = search.TagIndex.get_by_id('buildset:a')
    self.assertIsNotNone(index)
    self.assertEqual(len(index.entries), 2)
    self.assertEqual(index.entries[0].build_id, results[1][0].key.id())
    self.assertEqual(index.entries[0].bucket, results[1][0].bucket)
    self.assertEqual(index.entries[1].build_id, results[0][0].key.id())
    self.assertEqual(index.entries[1].bucket, results[0][0].bucket)

  def test_add_many_invalid_input(self):
    results = creation.add_many_async([
        creation.BuildRequest(
            project=self.chromium_project_id,
            bucket='chromium',
            tags=['buildset:a'],
        ),
        creation.BuildRequest(
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

    index = search.TagIndex.get_by_id('buildset:a')
    self.assertIsNotNone(index)
    self.assertEqual(len(index.entries), 1)
    self.assertEqual(index.entries[0].build_id, results[0][0].key.id())
    self.assertEqual(index.entries[0].bucket, results[0][0].bucket)

  def test_add_many_auth_error(self):
    self.mock_cannot(user.Action.ADD_BUILD, bucket='forbidden')
    with self.assertRaises(auth.AuthorizationError):
      creation.add_many_async([
          creation.BuildRequest(
              project=self.chromium_project_id,
              bucket='chromium',
              tags=['buildset:a'],
          ),
          creation.BuildRequest(
              project='forbidden',
              bucket='forbidden',
              tags=['buildset:a'],
          ),
      ]).get_result()

    index = search.TagIndex.get_by_id('buildset:a')
    self.assertIsNone(index)

  def test_add_many_with_client_op_id(self):
    req1 = creation.BuildRequest(
        project=self.chromium_project_id,
        bucket='chromium',
        tags=['buildset:a'],
        client_operation_id='0',
    )
    req2 = creation.BuildRequest(
        project=self.chromium_project_id,
        bucket='chromium',
        tags=['buildset:a'],
    )
    creation.add_async(req1).get_result()
    creation.add_many_async([req1, req2]).get_result()

    # Build for req1 must be added only once.
    idx = search.TagIndex.get_by_id('buildset:a')
    self.assertEqual(len(idx.entries), 2)
    self.assertEqual(idx.entries[0].bucket, 'chromium')

  @mock.patch('search.add_to_tag_index_async', autospec=True)
  def test_add_with_tag_index_contention(self, add_to_tag_index_async):
    self.chromium_bucket.swarming.MergeFrom(self.chromium_swarming)

    def mock_create_task_async(build, build_number):
      build.swarming_hostname = 'swarming.example.com'
      build.swarming_task_id = str(build_number)
      return future(None)

    swarming.create_task_async.side_effect = mock_create_task_async
    add_to_tag_index_async.side_effect = Exception('contention')
    swarming.cancel_task_async.side_effect = [
        future(None), future_exception(Exception())
    ]

    with self.assertRaisesRegexp(Exception, 'contention'):
      creation.add_many_async([
          creation.BuildRequest(
              project=self.chromium_project_id,
              bucket='chromium',
              parameters={model.BUILDER_PARAMETER: 'infra'},
              tags=['buildset:a'],
          ),
          creation.BuildRequest(
              project=self.chromium_project_id,
              bucket='chromium',
              parameters={model.BUILDER_PARAMETER: 'infra'},
              tags=['buildset:a'],
          ),
      ]).get_result()

    swarming.cancel_task_async.assert_any_call('swarming.example.com', '1')
    swarming.cancel_task_async.assert_any_call('swarming.example.com', '2')

  def test_retry(self):
    self.test_build.canary_preference = model.CanaryPreference.CANARY
    self.test_build.initial_tags = ['x:x']
    self.test_build.tags = self.test_build.initial_tags + ['y:y']
    self.test_build.put()
    build = creation.retry(self.test_build.key.id())
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
    build = creation.retry(self.test_build.key.id())
    self.assertIsNotNone(build)
    self.assertIsNotNone(build.key)
    self.assertNotEqual(build.key.id(), self.test_build.key.id())
    self.assertEqual(build.bucket, self.test_build.bucket)
    self.assertEqual(build.parameters, self.test_build.parameters)
    self.assertEqual(build.retry_of, self.test_build.key.id())

  def test_retry_not_found(self):
    with self.assertRaises(errors.BuildNotFoundError):
      creation.retry(2)
