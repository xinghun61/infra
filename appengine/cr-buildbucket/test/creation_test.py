# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime

from components import auth
from components import utils
from google.appengine.ext import ndb
from google.protobuf import struct_pb2
from testing_utils import testing
import mock

from proto import build_pb2
from proto import common_pb2
from proto import rpc_pb2
from proto import service_config_pb2
from test import test_util
import bbutil
import config
import creation
import errors
import model
import search
import user

future = test_util.future


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
    self.now = datetime.datetime(2015, 1, 1)
    self.patch('components.utils.utcnow', side_effect=lambda: self.now)

    self.chromium_try = test_util.parse_bucket_cfg(
        '''
        name: "luci.chromium.try"
        swarming {
          builders {
            name: "linux"
            build_numbers: YES
            swarming_host: "chromium-swarm.appspot.com"
            recipe {
              name: "recipe"
              cipd_package: "infra/recipe_bundle"
              cipd_version: "refs/heads/master"
            }
          }
          builders {
            name: "mac"
            swarming_host: "chromium-swarm.appspot.com"
            recipe {
              name: "recipe"
              cipd_package: "infra/recipe_bundle"
              cipd_version: "refs/heads/master"
            }
          }
          builders {
            name: "win"
            swarming_host: "chromium-swarm.appspot.com"
            recipe {
              name: "recipe"
              cipd_package: "infra/recipe_bundle"
              cipd_version: "refs/heads/master"
            }
          }
        }
        '''
    )
    config.put_bucket('chromium', 'a' * 40, self.chromium_try)
    self.create_sync_task = self.patch(
        'swarming.create_sync_task',
        autospec=True,
        return_value={'is_payload': True},
    )
    self.patch('swarming.cancel_task_async', return_value=future(None))

    self.patch(
        'google.appengine.api.app_identity.get_default_version_hostname',
        autospec=True,
        return_value='buildbucket.example.com'
    )

    self.patch('tq.enqueue_async', autospec=True, return_value=future(None))
    self.patch(
        'config.get_settings_async',
        autospec=True,
        return_value=future(service_config_pb2.SettingsCfg())
    )

    self.patch('creation._should_update_builder', side_effect=lambda p: p > 0.5)
    self.patch('creation._should_be_canary', side_effect=lambda p: p > 50)

    self.patch('search.TagIndex.random_shard_index', return_value=0)

  @contextlib.contextmanager
  def mutate_builder_cfg(self):
    yield self.chromium_try.swarming.builders[0]
    config.put_bucket('chromium', 'a' * 40, self.chromium_try)

  def build_request(self, schedule_build_request_fields=None, **kwargs):
    schedule_build_request_fields = schedule_build_request_fields or {}
    sbr = rpc_pb2.ScheduleBuildRequest(**schedule_build_request_fields)
    sbr.builder.project = sbr.builder.project or 'chromium'
    sbr.builder.bucket = sbr.builder.bucket or 'try'
    sbr.builder.builder = sbr.builder.builder or 'linux'
    return creation.BuildRequest(schedule_build_request=sbr, **kwargs)

  def add(self, *args, **kwargs):
    br = self.build_request(*args, **kwargs)
    return creation.add_async(br).get_result()

  def test_add(self):
    builder_id = build_pb2.BuilderID(
        project='chromium',
        bucket='try',
        builder='linux',
    )
    build = self.add(dict(builder=builder_id))
    self.assertIsNotNone(build.key)
    self.assertIsNotNone(build.key.id())

    build = build.key.get()
    self.assertEqual(build.proto.id, build.key.id())
    self.assertEqual(build.proto.builder, builder_id)
    self.assertEqual(
        build.proto.created_by,
        auth.get_current_identity().to_bytes()
    )

    self.assertEqual(build.proto.builder.project, 'chromium')
    self.assertEqual(build.proto.builder.bucket, 'try')
    self.assertEqual(build.proto.builder.builder, 'linux')
    self.assertEqual(build.created_by, auth.get_current_identity())

  def test_non_existing_builder(self):
    builder_id = build_pb2.BuilderID(
        project='chromium',
        bucket='try',
        builder='non-existing',
    )
    req = self.build_request(dict(builder=builder_id))
    (_, ex), = creation.add_many_async([req]).get_result()
    self.assertIsInstance(ex, errors.BuilderNotFoundError)

  def test_critical(self):
    build = self.add(dict(critical=common_pb2.YES))
    self.assertEqual(build.proto.critical, common_pb2.YES)

  def test_canary_in_request(self):
    build = self.add(dict(canary=common_pb2.YES))
    self.assertTrue(build.proto.canary)

  def test_canary_in_builder(self):
    with self.mutate_builder_cfg() as cfg:
      cfg.task_template_canary_percentage.value = 100

    build = self.add()
    self.assertTrue(build.proto.canary)

  def test_properties(self):
    props = {'foo': 'bar', 'qux': 1}
    prop_struct = bbutil.dict_to_struct(props)
    build = self.add(dict(properties=prop_struct))
    actual = struct_pb2.Struct()
    actual.ParseFromString(build.input_properties_bytes)

    expected = bbutil.dict_to_struct(props)
    expected['recipe'] = 'recipe'
    self.assertEqual(actual, expected)
    self.assertEqual(
        build.parse_infra().buildbucket.requested_properties, prop_struct
    )
    self.assertEqual(build.parameters.get(model.PROPERTIES_PARAMETER), props)

  def test_experimental(self):
    build = self.add(dict(experimental=common_pb2.YES))
    self.assertTrue(build.proto.input.experimental)
    self.assertEqual(build.parse_infra().swarming.priority, 60)

  def test_non_experimental(self):
    build = self.add(dict(experimental=common_pb2.NO))
    self.assertFalse(build.proto.input.experimental)
    self.assertEqual(build.parse_infra().swarming.priority, 30)

  def test_configured_caches(self):
    with self.mutate_builder_cfg() as cfg:
      cfg.caches.add(
          path='required',
          name='1',
      )
      cfg.caches.add(
          path='optional',
          name='1',
          wait_for_warm_cache_secs=60,
      )

    caches = self.add().parse_infra().swarming.caches
    self.assertIn(
        build_pb2.BuildInfra.Swarming.CacheEntry(
            path='required',
            name='1',
            wait_for_warm_cache=dict(),
        ),
        caches,
    )
    self.assertIn(
        build_pb2.BuildInfra.Swarming.CacheEntry(
            path='optional',
            name='1',
            wait_for_warm_cache=dict(seconds=60),
        ),
        caches,
    )

  def test_builder_cache(self):
    caches = self.add().parse_infra().swarming.caches

    self.assertIn(
        build_pb2.BuildInfra.Swarming.CacheEntry(
            path='builder',
            name=(
                'builder_ccadafffd20293e0378d1f94d214c63a0f8342d1161454ef0acf'
                'a0405178106b_v2'
            ),
            wait_for_warm_cache=dict(seconds=240),
        ),
        caches,
    )

  def test_builder_cache_overridden(self):
    with self.mutate_builder_cfg() as cfg:
      cfg.caches.add(
          path='builder',
          name='builder',
      )

    caches = self.add().parse_infra().swarming.caches
    self.assertIn(
        build_pb2.BuildInfra.Swarming.CacheEntry(
            path='builder',
            name='builder',
            wait_for_warm_cache=dict(),
        ),
        caches,
    )

  def test_configured_timeouts(self):
    with self.mutate_builder_cfg() as cfg:
      cfg.expiration_secs = 60
      cfg.execution_timeout_secs = 120

    build = self.add()
    self.assertEqual(build.proto.scheduling_timeout.seconds, 60)
    self.assertEqual(build.proto.execution_timeout.seconds, 120)

  def test_dimensions(self):
    dims = [
        common_pb2.RequestedDimension(key='d', value='1'),
        common_pb2.RequestedDimension(
            key='d', value='1', expiration=dict(seconds=60)
        ),
    ]
    build = self.add(dict(dimensions=dims))

    infra = build.parse_infra()
    self.assertEqual(list(infra.buildbucket.requested_dimensions), dims)
    self.assertEqual(list(infra.swarming.task_dimensions), dims)

  def test_dimensions_in_builder(self):
    with self.mutate_builder_cfg() as cfg:
      cfg.dimensions[:] = [
          '60:a:0',
          '0:a:1',
          'b:0',
          'tombstone:',
      ]

    dims = [
        common_pb2.RequestedDimension(
            key='b', value='1', expiration=dict(seconds=60)
        ),
        common_pb2.RequestedDimension(key='d', value='1'),
    ]
    build = self.add(dict(dimensions=dims))

    infra = build.parse_infra()
    self.assertEqual(list(infra.buildbucket.requested_dimensions), dims)
    self.assertEqual(
        list(infra.swarming.task_dimensions), [
            common_pb2.RequestedDimension(
                key='a',
                value='1',
                expiration=dict(seconds=0),
            ),
            common_pb2.RequestedDimension(
                key='a',
                value='0',
                expiration=dict(seconds=60),
            ),
            common_pb2.RequestedDimension(
                key='b',
                value='1',
                expiration=dict(seconds=60),
            ),
            common_pb2.RequestedDimension(key='d', value='1'),
        ]
    )

  def test_notify(self):
    build = self.add(
        dict(
            notify=dict(
                pubsub_topic='projects/p/topics/t',
                user_data='hello',
            )
        ),
    )
    self.assertEqual(build.pubsub_callback.topic, 'projects/p/topics/t')
    self.assertEqual(build.pubsub_callback.user_data, 'hello')

  def test_gitiles_commit(self):
    gitiles_commit = common_pb2.GitilesCommit(
        host='gitiles.example.com',
        project='chromium/src',
        ref='refs/heads/master',
        id='b7a757f457487cd5cfe2dae83f65c5bc10e288b7',
        position=1,
    )

    build = self.add(dict(gitiles_commit=gitiles_commit))
    bs = (
        'commit/gitiles/gitiles.example.com/chromium/src/+/'
        'b7a757f457487cd5cfe2dae83f65c5bc10e288b7'
    )
    self.assertIn('buildset:' + bs, build.tags)
    self.assertIn('gitiles_ref:refs/heads/master', build.tags)

  def test_gitiles_commit_without_id(self):
    gitiles_commit = common_pb2.GitilesCommit(
        host='gitiles.example.com',
        project='chromium/src',
        ref='refs/heads/master',
    )

    build = self.add(dict(gitiles_commit=gitiles_commit))
    self.assertFalse(any(t.startswith('buildset:commit') for t in build.tags))
    self.assertFalse(any(t.startswith('gititles_ref:') for t in build.tags))

  def test_gerrit_change(self):
    cl = common_pb2.GerritChange(
        host='gerrit.example.com',
        change=1234,
        patchset=5,
    )
    build = self.add(dict(gerrit_changes=[cl]))
    self.assertEqual(build.proto.input.gerrit_changes[:], [cl])
    bs = 'patch/gerrit/gerrit.example.com/1234/5'
    self.assertIn('buildset:' + bs, build.tags)

  def test_priority(self):
    build = self.add(dict(priority=42))
    self.assertEqual(build.parse_infra().swarming.priority, 42)

  def test_update_builders(self):
    recently = self.now - datetime.timedelta(minutes=1)
    while_ago = self.now - datetime.timedelta(minutes=61)
    ndb.put_multi([
        model.Builder(id='chromium:try:linux', last_scheduled=recently),
        model.Builder(id='chromium:try:mac', last_scheduled=while_ago),
    ])

    creation.add_many_async([
        self.build_request(dict(builder=dict(builder='linux'))),
        self.build_request(dict(builder=dict(builder='mac'))),
        self.build_request(dict(builder=dict(builder='win'))),
    ]).get_result()

    builders = model.Builder.query().fetch()
    self.assertEqual(len(builders), 3)
    self.assertEqual(builders[0].key.id(), 'chromium:try:linux')
    self.assertEqual(builders[0].last_scheduled, recently)
    self.assertEqual(builders[1].key.id(), 'chromium:try:mac')
    self.assertEqual(builders[1].last_scheduled, self.now)
    self.assertEqual(builders[2].key.id(), 'chromium:try:win')
    self.assertEqual(builders[2].last_scheduled, self.now)

  def test_request_id(self):
    build = self.add(dict(request_id='1'))
    build2 = self.add(dict(request_id='1'))
    self.assertIsNotNone(build.key)
    self.assertEqual(build, build2)

  def test_leasing(self):
    build = self.add(
        lease_expiration_date=utils.utcnow() + datetime.timedelta(seconds=10),
    )
    self.assertTrue(build.is_leased)
    self.assertGreater(build.lease_expiration_date, utils.utcnow())
    self.assertIsNotNone(build.lease_key)

  def test_builder_tag(self):
    build = self.add(dict(builder=dict(builder='linux')))
    self.assertTrue('builder:linux' in build.tags)

  def test_builder_tag_coincide(self):
    build = self.add(
        dict(
            builder=dict(builder='linux'),
            tags=[dict(key='builder', value='linux')],
        )
    )
    self.assertIn('builder:linux', build.tags)

  def test_buildset_index(self):
    build = self.add(
        dict(
            tags=[
                dict(key='buildset', value='foo'),
                dict(key='buildset', value='bar'),
            ]
        )
    )

    for t in ('buildset:foo', 'buildset:bar'):
      index = search.TagIndex.get_by_id(t)
      self.assertIsNotNone(index)
      self.assertEqual(len(index.entries), 1)
      self.assertEqual(index.entries[0].build_id, build.key.id())
      self.assertEqual(index.entries[0].bucket_id, build.bucket_id)

  def test_buildset_index_with_request_id(self):
    build = self.add(
        dict(
            tags=[dict(key='buildset', value='foo')],
            request_id='0',
        )
    )

    index = search.TagIndex.get_by_id('buildset:foo')
    self.assertIsNotNone(index)
    self.assertEqual(len(index.entries), 1)
    self.assertEqual(index.entries[0].build_id, build.key.id())
    self.assertEqual(index.entries[0].bucket_id, build.bucket_id)

  def test_buildset_index_existing(self):
    search.TagIndex(
        id='buildset:foo',
        entries=[
            search.TagIndexEntry(
                build_id=int(2**63 - 1),
                bucket_id='chromium/try',
            ),
            search.TagIndexEntry(
                build_id=0,
                bucket_id='chromium/try',
            ),
        ]
    ).put()
    build = self.add(dict(tags=[dict(key='buildset', value='foo')]))
    index = search.TagIndex.get_by_id('buildset:foo')
    self.assertIsNotNone(index)
    self.assertEqual(len(index.entries), 3)
    self.assertIn(build.key.id(), [e.build_id for e in index.entries])
    self.assertIn(build.bucket_id, [e.bucket_id for e in index.entries])

  def test_many(self):
    results = creation.add_many_async([
        self.build_request(dict(tags=[dict(key='buildset', value='a')])),
        self.build_request(dict(tags=[dict(key='buildset', value='a')])),
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
    self.assertEqual(index.entries[0].bucket_id, results[1][0].bucket_id)
    self.assertEqual(index.entries[1].build_id, results[0][0].key.id())
    self.assertEqual(index.entries[1].bucket_id, results[0][0].bucket_id)

  def test_many_with_request_id(self):
    req1 = self.build_request(
        dict(
            tags=[dict(key='buildset', value='a')],
            request_id='0',
        ),
    )
    req2 = self.build_request(dict(tags=[dict(key='buildset', value='a')]))
    creation.add_async(req1).get_result()
    creation.add_many_async([req1, req2]).get_result()

    # Build for req1 must be added only once.
    idx = search.TagIndex.get_by_id('buildset:a')
    self.assertEqual(len(idx.entries), 2)
    self.assertEqual(idx.entries[0].bucket_id, 'chromium/try')

  def test_create_sync_task(self):
    expected_ex1 = errors.InvalidInputError()

    def create_sync_task(build, *_args, **_kwargs):
      if 'buildset:a' in build.tags:
        raise expected_ex1

    self.create_sync_task.side_effect = create_sync_task

    ((b1, ex1), (b2, ex2)) = creation.add_many_async([
        self.build_request(dict(tags=[dict(key='buildset', value='a')])),
        self.build_request(dict(tags=[dict(key='buildset', value='b')])),
    ]).get_result()

    self.assertEqual(ex1, expected_ex1)
    self.assertIsNone(b1)
    self.assertIsNone(ex2)
    self.assertIsNotNone(b2)
