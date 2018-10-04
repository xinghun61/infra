# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import contextlib
import copy
import datetime
import json
import logging

from components import utils
utils.fix_protobuf_package()

from google import protobuf
from google.protobuf import json_format

from components import auth
from components import net
from components import utils
from testing_utils import testing
from webob import exc
import mock
import webapp2

from third_party import annotations_pb2

from proto import build_pb2
from proto import common_pb2
from proto import launcher_pb2
from proto import step_pb2
from proto.config import project_config_pb2
from proto.config import service_config_pb2
from swarming import isolate
from swarming import swarming
from test.test_util import future, future_exception, ununicide
import annotations
import errors
import model
import user

LINUX_CHROMIUM_REL_NG_CACHE_NAME = (
    'builder_980988014eb33bf5578a0f44e123402888e39083523bfd9214fea0c8a080db17'
)


class BaseTest(testing.AppengineTestCase):

  def setUp(self):
    super(BaseTest, self).setUp()
    user.clear_request_cache()

    self.patch(
        'notifications.enqueue_tasks_async',
        autospec=True,
        return_value=future(None)
    )
    self.patch(
        'bq.enqueue_pull_task_async', autospec=True, return_value=future(None)
    )

    self.now = datetime.datetime(2015, 11, 30)
    self.patch(
        'components.utils.utcnow', autospec=True, side_effect=lambda: self.now
    )

    self.settings = service_config_pb2.SettingsCfg(
        swarming=service_config_pb2.SwarmingSettings(
            milo_hostname='milo.example.com',
        ),
    )
    self.patch(
        'config.get_settings_async',
        autospec=True,
        return_value=future(self.settings)
    )


class SwarmingTest(BaseTest):

  def setUp(self):
    super(SwarmingTest, self).setUp()

    self.json_response = None
    self.net_err_response = None
    self.maxDiff = None

    def json_request_async(*_, **__):
      if self.net_err_response is not None:
        return future_exception(self.net_err_response)
      if self.json_response is not None:
        return future(self.json_response)
      self.fail('unexpected outbound request')  # pragma: no cover

    self.patch(
        'components.net.json_request_async',
        autospec=True,
        side_effect=json_request_async
    )

    bucket_cfg_text = '''
      name: "luci.chromium.try"
      swarming {
        hostname: "chromium-swarm.appspot.com"
        builders {
          name: "linux_chromium_rel_ng"
          swarming_tags: "buildertag:yes"
          swarming_tags: "commontag:yes"
          dimensions: "cores:8"
          dimensions: "os:Ubuntu"
          dimensions: "pool:Chrome"
          priority: 108
          build_numbers: YES
          service_account: "robot@example.com"
          recipe {
            repository: "https://example.com/repo"
            name: "recipe"
            properties_j: "predefined-property:\\\"x\\\""
            properties_j: "predefined-property-bool:true"
          }
          caches {
            path: "a"
            name: "a"
          }
          caches {
            path: "git_cache"
            name: "git_chromium"
          }
          caches {
            path: "out"
            name: "build_chromium"
          }
        }
        builders {
          name: "linux_chromium_rel_ng cipd"
          swarming_tags: "buildertag:yes"
          swarming_tags: "commontag:yes"
          dimensions: "cores:8"
          dimensions: "os:Ubuntu"
          dimensions: "pool:Chrome"
          priority: 108
          build_numbers: YES
          service_account: "robot@example.com"
          recipe {
            cipd_package: "infra/recipe_bundles/chromium.googlesource.com/chromium/tools/build"
            cipd_version: "refs/heads/master"
            name: "recipe"
            properties_j: "predefined-property:\\\"x\\\""
            properties_j: "predefined-property-bool:true"
            properties: "buildername:linux_chromium_rel_ng"
          }
          caches {
            path: "a"
            name: "a"
          }
          caches {
            path: "git_cache"
            name: "git_chromium"
          }
          caches {
            path: "out"
            name: "build_chromium"
          }
        }
      }
    '''
    self.bucket_cfg = project_config_pb2.Bucket()
    protobuf.text_format.Merge(bucket_cfg_text, self.bucket_cfg)

    self.patch(
        'config.get_bucket_async',
        autospec=True,
        return_value=future(('chromium', self.bucket_cfg))
    )

    self.task_template = {
        'name':
            'buildbucket:${bucket}:${builder}',
        'priority':
            '100',
        'tags': [
            (
                'log_location:logdog://luci-logdog-dev.appspot.com/${project}/'
                'buildbucket/${hostname}/${build_id}/+/annotations'
            ),
            'luci_project:${project}',
        ],
        'task_slices': [{
            'expiration_secs': '3600',
            'properties': {
                'execution_timeout_secs':
                    '3600',
                'extra_args': [
                    'cook',
                    '-repository',
                    '${repository}',
                    '-revision',
                    '${revision}',
                    '-recipe',
                    '${recipe}',
                    '-properties',
                    '${properties_json}',
                    '-logdog-project',
                    '${project}',
                ],
                'caches': [{
                    'path': '${cache_dir}/builder',
                    'name': 'builder_${builder_hash}',
                    'wait_for_warm_cache_secs': 60,
                }],
                'cipd_input': {
                    'packages': [
                        {
                            'package_name': 'infra/test/bar/${os_ver}',
                            'path': '.',
                            'version': 'latest',
                        },
                        {
                            'package_name': 'infra/test/foo/${platform}',
                            'path': 'third_party',
                            'version': 'stable',
                        },
                    ],
                },
            },
            'wait_for_capacity': False,
        },],
        'numerical_value_for_coverage_in_format_obj':
            42,
    }
    self.task_template_canary = self.task_template.copy()
    self.task_template_canary['name'] += '-canary'

    def get_self_config_async(path, *_args, **_kwargs):
      if path not in ('swarming_task_template.json',
                      'swarming_task_template_canary.json'):  # pragma: no cover
        self.fail()

      if path == 'swarming_task_template.json':
        template = self.task_template
      else:
        template = self.task_template_canary
      return future((
          'template_rev', json.dumps(template) if template is not None else None
      ))

    self.patch(
        'components.config.get_self_config_async',
        side_effect=get_self_config_async
    )

    self.patch('components.auth.delegate_async', return_value=future('blah'))
    self.patch(
        'google.appengine.api.app_identity.get_default_version_hostname',
        return_value='cr-buildbucket.appspot.com'
    )

  def test_validate_build_parameters(self):
    bad = [
        {'properties': []},
        {'properties': {'buildername': 'bar'}},
        {'properties': {'blamelist': ['a@example.com']}},
        {'changes': 0},
        {'changes': [0]},
        {'changes': [{'author': 0}]},
        {'changes': [{'author': {}}]},
        {'changes': [{'author': {'email': 0}}]},
        {'changes': [{'author': {'email': ''}}]},
        {'changes': [{'author': {'email': 'a@example.com'}, 'repo_url': 0}]},
        {'swarming': []},
        {'swarming': {'junk': 1}},
        {'swarming': {'recipe': []}},
    ]
    for p in bad:
      logging.info('testing %s', p)
      p[model.BUILDER_PARAMETER] = 'foo'
      with self.assertRaises(errors.InvalidInputError):
        swarming.validate_build_parameters(p[model.BUILDER_PARAMETER], p)

    swarming.validate_build_parameters(
        'foo', {
            model.BUILDER_PARAMETER: 'foo',
            'properties': {'blamelist': ['a@example.com']},
            'changes': [{'author': {'email': 'a@example.com'}}],
        }
    )

  def test_shared_cache(self):
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.caches.add(path='builder', name='shared_builder_cache')

    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    task_def = swarming.prepare_task_def_async(build).get_result()

    self.assertEqual(
        task_def['task_slices'][0]['properties']['caches'], [
            {'path': 'cache/a', 'name': 'a'},
            {'path': 'cache/builder', 'name': 'shared_builder_cache'},
            {'path': 'cache/git_cache', 'name': 'git_chromium'},
            {'path': 'cache/out', 'name': 'build_chromium'},
        ]
    )

  def test_dimensions_and_cache_fallback(self):
    # Creates 4 task_slices by modifying the buildercfg in 2 ways:
    # - Add two named caches, one expiring at 60 seconds, one at 360 seconds.
    # - Add an optional builder dimension, expiring at 120 seconds.
    #
    # This ensures the combination of these features works correctly, and that
    # multiple 'caches' dimensions can be injected.
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.caches.add(
        path='builder',
        name='shared_builder_cache',
        wait_for_warm_cache_secs=60,
    )
    builder_cfg.caches.add(
        path='second',
        name='second_cache',
        wait_for_warm_cache_secs=360,
    )
    builder_cfg.dimensions.append("120:opt:ional")

    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    task_def = swarming.prepare_task_def_async(build).get_result()

    self.assertEqual(4, len(task_def['task_slices']))
    for t in task_def['task_slices']:
      # They all use the same cache definitions.
      self.assertEqual(
          t['properties']['caches'], [
              {'path': u'cache/a', 'name': u'a'},
              {'path': u'cache/builder', 'name': u'shared_builder_cache'},
              {'path': u'cache/git_cache', 'name': u'git_chromium'},
              {'path': u'cache/out', 'name': u'build_chromium'},
              {'path': u'cache/second', 'name': u'second_cache'},
          ]
      )

    # But the dimensions are different. 'opt' and 'caches' are injected.
    self.assertEqual(
        task_def['task_slices'][0]['properties']['dimensions'], [
            {u'key': u'caches', u'value': u'second_cache'},
            {u'key': u'caches', u'value': u'shared_builder_cache'},
            {u'key': u'cores', u'value': u'8'},
            {u'key': u'opt', u'value': u'ional'},
            {u'key': u'os', u'value': u'Ubuntu'},
            {u'key': u'pool', u'value': u'Chrome'},
        ]
    )
    self.assertEqual(task_def['task_slices'][0]['expiration_secs'], '60')

    # One 'caches' expired. 'opt' and one 'caches' are still injected.
    self.assertEqual(
        task_def['task_slices'][1]['properties']['dimensions'], [
            {u'key': u'caches', u'value': u'second_cache'},
            {u'key': u'cores', u'value': u'8'},
            {u'key': u'opt', u'value': u'ional'},
            {u'key': u'os', u'value': u'Ubuntu'},
            {u'key': u'pool', u'value': u'Chrome'},
        ]
    )
    # 120-60
    self.assertEqual(task_def['task_slices'][1]['expiration_secs'], '60')

    # 'opt' expired, one 'caches' remains.
    self.assertEqual(
        task_def['task_slices'][2]['properties']['dimensions'], [
            {u'key': u'caches', u'value': u'second_cache'},
            {u'key': u'cores', u'value': u'8'},
            {u'key': u'os', u'value': u'Ubuntu'},
            {u'key': u'pool', u'value': u'Chrome'},
        ]
    )
    # 360-120
    self.assertEqual(task_def['task_slices'][2]['expiration_secs'], '240')

    # The cold fallback; the last 'caches' expired.
    self.assertEqual(
        task_def['task_slices'][3]['properties']['dimensions'], [
            {u'key': u'cores', u'value': u'8'},
            {u'key': u'os', u'value': u'Ubuntu'},
            {u'key': u'pool', u'value': u'Chrome'},
        ]
    )
    # 3600-360
    self.assertEqual(task_def['task_slices'][3]['expiration_secs'], '3240')

  def test_cache_fallback_fail_multiple_task_slices(self):
    # Make it so the swarming task template has two task_slices, which is
    # incompatible with a builder using wait_for_warm_cache_secs.
    self.task_template['task_slices'].append(
        self.task_template['task_slices'][0]
    )
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.caches.add(
        path='builder',
        name='shared_builder_cache',
        wait_for_warm_cache_secs=60,
    )

    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    with self.assertRaises(errors.InvalidInputError):
      swarming.prepare_task_def_async(build).get_result()

  def test_recipe_cipd_package(self):
    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng cipd',
        },
        tags=['builder:linux_chromium_rel_ng cipd'],
    )

    task_def = swarming.prepare_task_def_async(build).get_result()

    self.assertIn(
        {
            'package_name': (
                'infra/recipe_bundles/chromium.googlesource.com/chromium/tools'
                '/build'
            ),
            'path':
                'kitchen-checkout',
            'version':
                'refs/heads/master',
        },
        task_def['task_slices'][0]['properties']['cipd_input']['packages'],
    )

  def test_execution_timeout(self):
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.execution_timeout_secs = 120

    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    task_def = swarming.prepare_task_def_async(build).get_result()

    self.assertEqual(
        task_def['task_slices'][0]['properties']['execution_timeout_secs'],
        '120'
    )

    builder_cfg.execution_timeout_secs = 60
    task_def = swarming.prepare_task_def_async(build).get_result()
    self.assertEqual(
        task_def['task_slices'][0]['properties']['execution_timeout_secs'], '60'
    )

  def test_expiration(self):
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.expiration_secs = 120

    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    task_def = swarming.prepare_task_def_async(build).get_result()

    self.assertEqual(2, len(task_def['task_slices']))
    self.assertEqual(task_def['task_slices'][0]['expiration_secs'], '60')
    self.assertEqual(task_def['task_slices'][1]['expiration_secs'], '60')

    builder_cfg.expiration_secs = 60
    task_def = swarming.prepare_task_def_async(build).get_result()
    self.assertEqual(task_def['task_slices'][0]['expiration_secs'], '60')
    self.assertEqual(task_def['task_slices'][1]['expiration_secs'], '60')

  def test_auto_builder_dimension(self):
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.auto_builder_dimension = project_config_pb2.YES

    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    task_def = swarming.prepare_task_def_async(build).get_result()
    self.assertEqual(
        task_def['task_slices'][0]['properties']['dimensions'], [
            {u'key': u'builder', u'value': u'linux_chromium_rel_ng'},
            {u'key': u'caches', u'value': LINUX_CHROMIUM_REL_NG_CACHE_NAME},
            {u'key': u'cores', u'value': u'8'},
            {u'key': u'os', u'value': u'Ubuntu'},
            {u'key': u'pool', u'value': u'Chrome'},
        ]
    )

    # But don't override if "builder" dimension is already set.
    builder_cfg.dimensions.append('builder:custom')
    task_def = swarming.prepare_task_def_async(build).get_result()
    self.assertEqual(
        task_def['task_slices'][0]['properties']['dimensions'], [
            {u'key': u'builder', u'value': u'custom'},
            {u'key': u'caches', u'value': LINUX_CHROMIUM_REL_NG_CACHE_NAME},
            {u'key': u'cores', u'value': u'8'},
            {u'key': u'os', u'value': u'Ubuntu'},
            {u'key': u'pool', u'value': u'Chrome'},
        ]
    )

  def test_unset_dimension(self):
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.dimensions[:] = ['cores:']

    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    task_def = swarming.prepare_task_def_async(build).get_result()
    dim_keys = {
        d['key'] for d in task_def['task_slices'][0]['properties']['dimensions']
    }
    self.assertNotIn('cores', dim_keys)

  def test_is_migrating_builder_prod_async_no_master_name(self):
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.luci_migration_host = 'migration.example.com'
    build = mkBuild()
    self.assertIsNone(
        swarming._is_migrating_builder_prod_async(builder_cfg,
                                                  build).get_result()
    )
    self.assertFalse(net.json_request_async.called)

  def test_is_migrating_builder_prod_async_no_host(self):
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    build = mkBuild(
        parameters={'properties': {'mastername': 'tryserver.chromium.linux'}}
    )
    self.assertIsNone(
        swarming._is_migrating_builder_prod_async(builder_cfg,
                                                  build).get_result()
    )
    self.assertFalse(net.json_request_async.called)

  def test_is_migrating_builder_prod_async_prod(self):
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.luci_migration_host = 'migration.example.com'
    build = mkBuild(
        parameters={'properties': {'mastername': 'tryserver.chromium.linux'}}
    )
    self.json_response = {'luci_is_prod': True, 'bucket': 'luci.chromium.try'}
    self.assertTrue(
        swarming._is_migrating_builder_prod_async(builder_cfg,
                                                  build).get_result()
    )
    self.assertTrue(net.json_request_async.called)

  def test_is_migrating_builder_prod_async_mastername_in_builder(self):
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.luci_migration_host = 'migration.example.com'
    builder_cfg.recipe.properties_j.append(
        'mastername:"tryserver.chromium.linux"'
    )
    build = mkBuild()
    self.json_response = {'luci_is_prod': True, 'bucket': 'luci.chromium.try'}
    self.assertTrue(
        swarming._is_migrating_builder_prod_async(builder_cfg,
                                                  build).get_result()
    )
    self.assertTrue(net.json_request_async.called)

  def test_is_migrating_builder_prod_async_404(self):
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.luci_migration_host = 'migration.example.com'
    build = mkBuild(
        parameters={'properties': {'mastername': 'tryserver.chromium.linux'}}
    )

    self.net_err_response = net.NotFoundError('nope', 404, 'can\'t find it')
    self.assertIsNone(
        swarming._is_migrating_builder_prod_async(builder_cfg,
                                                  build).get_result()
    )

  def test_is_migrating_builder_prod_async_500(self):
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.luci_migration_host = 'migration.example.com'
    build = mkBuild(
        parameters={'properties': {'mastername': 'tryserver.chromium.linux'}}
    )

    self.net_err_response = net.Error('BOOM', 500, 'IT\'S BAD')
    self.assertIsNone(
        swarming._is_migrating_builder_prod_async(builder_cfg,
                                                  build).get_result()
    )

  def test_is_migrating_builder_prod_async_no_is_prod_in_response(self):
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.luci_migration_host = 'migration.example.com'
    build = mkBuild(
        parameters={'properties': {'mastername': 'tryserver.chromium.linux'}}
    )

    self.net_err_response = None
    self.json_response = {'foo': True}
    self.assertIsNone(
        swarming._is_migrating_builder_prod_async(builder_cfg,
                                                  build).get_result()
    )

  def test_create_task_async(self):
    self.patch(
        'components.auth.get_current_identity',
        autospec=True,
        return_value=auth.Identity('user', 'john@example.com')
    )
    self.patch(
        'swarming.swarming._is_migrating_builder_prod_async',
        autospec=True,
        return_value=future(True)
    )
    self.patch(
        'v2.tokens.generate_build_token',
        autospec=True,
        return_value='beeff00d',
    )

    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER:
                'linux_chromium_rel_ng',
            'properties': {'a': 'b'},
            'changes': [{
                'author': {'email': 'bob@example.com'},
                'repo_url': 'https://chromium.googlesource.com/chromium/src',
            }],
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    self.json_response = {
        'task_id': 'deadbeef',
        'request': {
            'task_slices': [{
                'expiration_secs': 3600,
                'properties': {
                    'execution_timeout_secs':
                        1800,
                    'dimensions': [
                        {'key': 'cores', 'value': '8'},
                        {'key': 'os', 'value': 'Ubuntu'},
                        {'key': 'pool', 'value': 'Chrome'},
                    ],
                },
            }],
            'tags': [
                'build_address:luci.chromium.try/linux_chromium_rel_ng/1',
                'builder:linux_chromium_rel_ng',
                'buildertag:yes',
                'commontag:yes',
                (
                    'log_location:logdog://luci-logdog-dev.appspot.com/'
                    'chromium/buildbucket/cr-buildbucket.appspot.com/1/+/'
                    'annotations'
                ),
                'priority:108',
                'recipe_name:recipe',
                'recipe_repository:https://example.com/repo',
            ],
            'service_account':
                'robot@example.com',
        },
    }

    swarming.create_task_async(build, 1).get_result()

    # Test swarming request.
    self.assertEqual(
        net.json_request_async.call_args[0][0],
        'https://chromium-swarm.appspot.com/_ah/api/swarming/v1/tasks/new'
    )
    actual_task_def = net.json_request_async.call_args[1]['payload']
    expected_secret_bytes = base64.b64encode(
        launcher_pb2.BuildSecrets(build_token='beeff00d').SerializeToString()
    )
    props_def = {
        'env': [{
            'key': 'BUILDBUCKET_EXPERIMENTAL',
            'value': 'FALSE',
        }],
        'execution_timeout_secs':
            '3600',
        'extra_args': [
            'cook',
            '-repository',
            'https://example.com/repo',
            '-revision',
            'HEAD',
            '-recipe',
            'recipe',
            '-properties',
            json.dumps(
                {
                    'a':
                        'b',
                    'blamelist': ['bob@example.com'],
                    'buildbucket': {
                        'hostname': 'cr-buildbucket.appspot.com',
                        'build': {
                            'project':
                                'chromium',
                            'bucket':
                                'luci.chromium.try',
                            'created_by':
                                'user:john@example.com',
                            'created_ts':
                                utils.datetime_to_timestamp(build.create_time),
                            'id':
                                '1',
                            'tags': [],
                        },
                    },
                    'buildername':
                        'linux_chromium_rel_ng',
                    'buildnumber':
                        1,
                    'predefined-property':
                        'x',
                    'predefined-property-bool':
                        True,
                    'repository':
                        'https://chromium.googlesource.com/chromium/src',
                    '$recipe_engine/runtime': {
                        'is_experimental': False,
                        'is_luci': True,
                    },
                },
                sort_keys=True,
            ),
            '-logdog-project',
            'chromium',
        ],
        'secret_bytes':
            expected_secret_bytes,
        'dimensions': [
            {'key': 'cores', 'value': '8'},
            {'key': 'os', 'value': 'Ubuntu'},
            {'key': 'pool', 'value': 'Chrome'},
        ],
        'caches': [
            {'path': 'cache/a', 'name': 'a'},
            {'path': 'cache/builder', 'name': LINUX_CHROMIUM_REL_NG_CACHE_NAME},
            {'path': 'cache/git_cache', 'name': 'git_chromium'},
            {'path': 'cache/out', 'name': 'build_chromium'},
        ],
        'cipd_input': {
            'packages': [
                {
                    'package_name': 'infra/test/bar/${os_ver}',
                    'path': '.',
                    'version': 'latest',
                },
                {
                    'package_name': 'infra/test/foo/${platform}',
                    'path': 'third_party',
                    'version': 'stable',
                },
            ],
        },
    }
    # The swarming template has fallback.
    props_def_first = copy.deepcopy(props_def)
    props_def_first[u'dimensions'].append({
        u'key': u'caches',
        u'value': LINUX_CHROMIUM_REL_NG_CACHE_NAME,
    })
    props_def_first[u'dimensions'].sort(key=lambda x: (x[u'key'], x[u'value']))
    expected_task_def = {
        'name':
            'buildbucket:luci.chromium.try:linux_chromium_rel_ng',
        'priority':
            '108',
        'tags': [
            'build_address:luci.chromium.try/linux_chromium_rel_ng/1',
            'buildbucket_bucket:luci.chromium.try',
            'buildbucket_build_id:1',
            'buildbucket_hostname:cr-buildbucket.appspot.com',
            'buildbucket_template_canary:0',
            'buildbucket_template_revision:template_rev',
            'builder:linux_chromium_rel_ng',
            'buildertag:yes',
            'commontag:yes',
            (
                'log_location:logdog://luci-logdog-dev.appspot.com/chromium/'
                'buildbucket/cr-buildbucket.appspot.com/1/+/annotations'
            ),
            'luci_project:chromium',
            'recipe_name:recipe',
            'recipe_repository:https://example.com/repo',
        ],
        'pool_task_template':
            'CANARY_NEVER',
        'task_slices': [
            {
                'expiration_secs': '60',
                'properties': props_def_first,
                'wait_for_capacity': False,
            },
            {
                'expiration_secs': '3540',
                'properties': props_def,
                'wait_for_capacity': False,
            },
        ],
        'pubsub_topic':
            'projects/testbed-test/topics/swarming',
        'pubsub_userdata':
            json.dumps({
                'created_ts': utils.datetime_to_timestamp(utils.utcnow()),
                'swarming_hostname': 'chromium-swarm.appspot.com',
                'build_id': 1L,
            },
                       sort_keys=True),
        'service_account':
            'robot@example.com',
        'numerical_value_for_coverage_in_format_obj':
            42,
    }
    self.assertEqual(ununicide(actual_task_def), expected_task_def)

    self.assertEqual(
        set(build.tags), {
            'build_address:luci.chromium.try/linux_chromium_rel_ng/1',
            'builder:linux_chromium_rel_ng',
            'swarming_dimension:cores:8',
            'swarming_dimension:os:Ubuntu',
            'swarming_dimension:pool:Chrome',
            'swarming_hostname:chromium-swarm.appspot.com',
            (
                'swarming_tag:build_address:luci.chromium.try/'
                'linux_chromium_rel_ng/1'
            ),
            'swarming_tag:builder:linux_chromium_rel_ng',
            'swarming_tag:buildertag:yes',
            'swarming_tag:commontag:yes',
            (
                'swarming_tag:log_location:'
                'logdog://luci-logdog-dev.appspot.com/'
                'chromium/buildbucket/cr-buildbucket.appspot.com/1/+/'
                'annotations'
            ),
            'swarming_tag:priority:108',
            'swarming_tag:recipe_name:recipe',
            'swarming_tag:recipe_repository:https://example.com/repo',
            'swarming_task_id:deadbeef',
        }
    )
    self.assertEqual(
        build.url, (
            'https://milo.example.com'
            '/p/chromium/builders/luci.chromium.try/linux_chromium_rel_ng/1'
        )
    )

    self.assertEqual(build.service_account, 'robot@example.com')

    self.assertEqual(build.logdog_hostname, 'luci-logdog-dev.appspot.com')
    self.assertEqual(build.logdog_project, 'chromium')
    self.assertEqual(
        build.logdog_prefix, 'buildbucket/cr-buildbucket.appspot.com/1'
    )
    self.assertEqual(
        build.parameters_actual['properties']['predefined-property'], 'x'
    )

    # Test delegation token params.
    self.assertEqual(
        auth.delegate_async.mock_calls, [
            mock.call(
                services=[u'https://chromium-swarm.appspot.com'],
                audience=[auth.Identity('user', 'test@localhost')],
                impersonate=auth.Identity('user', 'john@example.com'),
                tags=['buildbucket:bucket:luci.chromium.try'],
            )
        ]
    )

  def test_create_task_async_experimental(self):
    build = mkBuild(
        parameters={model.BUILDER_PARAMETER: 'linux_chromium_rel_ng'},
        experimental=True,
    )

    self.json_response = {
        'task_id': 'deadbeef',
        'request': {
            'task_slices': [{
                'expiration_secs': 3600,
                'properties': {'execution_timeout_secs': 1800},
            }],
            'tags': [
                'build_address:luci.chromium.try/linux_chromium_rel_ng/1',
                'builder:linux_chromium_rel_ng',
                'buildertag:yes',
                'priority:108',
                'recipe_name:recipe',
                'recipe_repository:https://example.com/repo',
            ],
            'service_account':
                'robot@example.com',
        },
    }

    swarming.create_task_async(build, 1).get_result()

    actual_task_def = net.json_request_async.call_args[1]['payload']
    self.assertEqual(actual_task_def['priority'], '216')
    self.assertIn({
        'key': 'BUILDBUCKET_EXPERIMENTAL',
        'value': 'TRUE',
    }, actual_task_def['task_slices'][0]['properties']['env'])

  def test_create_task_async_new_swarming_template_format(self):
    self.task_template = {
        'name':
            'buildbucket:${bucket}:${builder}',
        'priority':
            '100',
        'task_slices': [{
            'expiration_secs': '3600',
            'properties': {
                'execution_timeout_secs':
                    '3600',
                'extra_args': [
                    'cook',
                    '-repository',
                    '${repository}',
                    '-revision',
                    '${revision}',
                    '-recipe',
                    '${recipe}',
                    '-properties',
                    '${properties_json}',
                    '-logdog-project',
                    '${project}',
                ],
                'caches': [{
                    'path': '${cache_dir}/builder',
                    'name': 'builder_${builder_hash}'
                }],
                'cipd_input': {
                    'packages': [
                        {
                            'package_name': 'infra/test/bar/${os_ver}',
                            'path': '.',
                            'version': 'latest',
                        },
                        {
                            'package_name': 'infra/test/foo/${platform}',
                            'path': 'third_party',
                            'version': 'stable',
                        },
                    ],
                },
            },
        }],
        'tags': [
            (
                'log_location:logdog://luci-logdog-dev.appspot.com/${project}/'
                'buildbucket/${hostname}/${build_id}/+/annotations'
            ),
            'luci_project:${project}',
        ],
    }

    build = mkBuild(
        parameters={model.BUILDER_PARAMETER: 'linux_chromium_rel_ng'},
    )

    self.json_response = {
        'task_id': 'deadbeef',
        'request': {
            'task_slices': [{
                'expiration_secs': 3600,
                'properties': {'execution_timeout_secs': 1800},
            }],
            'tags': [
                'build_address:luci.chromium.try/linux_chromium_rel_ng/1',
                'builder:linux_chromium_rel_ng',
                'buildertag:yes',
                'priority:108',
                'recipe_name:recipe',
                'recipe_repository:https://example.com/repo',
            ],
            'service_account':
                'robot@example.com',
        },
    }

    swarming.create_task_async(build, 1).get_result()

    actual_task_def = net.json_request_async.call_args[1]['payload']
    self.assertEqual(actual_task_def['priority'], '108')
    self.assertIn({
        'key': 'BUILDBUCKET_EXPERIMENTAL',
        'value': 'FALSE',
    }, actual_task_def['task_slices'][0]['properties']['env'])

  def test_create_task_async_for_non_swarming_bucket(self):
    self.bucket_cfg.ClearField('swarming')
    build = mkBuild(
        parameters={model.BUILDER_PARAMETER: 'linux_chromium_rel_ng'},
        tags=['builder:linux_chromium_rel_ng'],
    )

    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

  def test_create_task_async_without_template(self):
    self.task_template = None
    self.task_template_canary = None

    build = mkBuild(
        parameters={model.BUILDER_PARAMETER: 'linux_chromium_rel_ng'},
        tags=['builder:linux_chromium_rel_ng'],
    )

    with self.assertRaises(swarming.TemplateNotFound):
      swarming.create_task_async(build).get_result()

  def test_create_task_async_bad_request(self):
    build = mkBuild()

    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

    with self.assertRaises(errors.BuilderNotFoundError):
      build.parameters = {
          model.BUILDER_PARAMETER: 'non-existent builder',
      }
      swarming.create_task_async(build).get_result()

    with self.assertRaises(errors.InvalidInputError):
      build.parameters[model.BUILDER_PARAMETER] = 2
      swarming.create_task_async(build).get_result()

  def test_create_task_async_max_dimensions(self):
    build = mkBuild(
        parameters={model.BUILDER_PARAMETER: 'linux_chromium_rel_ng'},
    )
    self.json_response = {
        'task_id': 'deadbeef',
    }
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.dimensions.append("60:opt1:ional")
    builder_cfg.dimensions.append("120:opt2:ional")
    builder_cfg.dimensions.append("240:opt3:ional")
    builder_cfg.dimensions.append("300:opt4:ional")
    builder_cfg.dimensions.append("360:opt5:ional")
    builder_cfg.dimensions.append("420:opt6:ional")
    swarming.create_task_async(build).get_result()

  def test_create_task_async_bad_request_dimensions(self):
    # One too much.
    build = mkBuild(
        parameters={model.BUILDER_PARAMETER: 'linux_chromium_rel_ng'},
    )
    self.json_response = {
        'task_id': 'deadbeef',
    }
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.dimensions.append("60:opt1:ional")
    builder_cfg.dimensions.append("120:opt2:ional")
    builder_cfg.dimensions.append("240:opt3:ional")
    builder_cfg.dimensions.append("300:opt4:ional")
    builder_cfg.dimensions.append("360:opt5:ional")
    builder_cfg.dimensions.append("420:opt6:ional")
    builder_cfg.dimensions.append("480:opt7:ional")
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

  def test_create_task_async_canary_template(self):
    self.patch(
        'v2.tokens.generate_build_token',
        autospec=True,
        return_value='beeff00d',
    )

    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
        },
        tags=['builder:linux_chromium_rel_ng'],
        canary_preference=model.CanaryPreference.CANARY,
    )

    self.json_response = {
        'task_id': 'deadbeef',
        'request': {
            'task_slices': [{
                'expiration_secs': 3600,
                'properties': {
                    'execution_timeout_secs':
                        1800,
                    'dimensions': [
                        {'key': 'cores', 'value': '8'},
                        {'key': 'os', 'value': 'Ubuntu'},
                        {'key': 'pool', 'value': 'Chrome'},
                    ],
                },
            }],
            'tags': [
                'builder:linux_chromium_rel_ng',
                'buildertag:yes',
                'commontag:yes',
                'priority:108',
                'recipe_name:recipe',
                'recipe_repository:https://example.com/repo',
            ],
        },
    }

    swarming.create_task_async(build).get_result()

    # Test swarming request.
    self.assertEqual(
        net.json_request_async.call_args[0][0],
        'https://chromium-swarm.appspot.com/_ah/api/swarming/v1/tasks/new'
    )
    actual_task_def = net.json_request_async.call_args[1]['payload']
    expected_secret_bytes = base64.b64encode(
        launcher_pb2.BuildSecrets(build_token='beeff00d').SerializeToString()
    )
    props_def = {
        'env': [{
            'key': 'BUILDBUCKET_EXPERIMENTAL',
            'value': 'FALSE',
        }],
        'execution_timeout_secs':
            '3600',
        'extra_args': [
            'cook',
            '-repository',
            'https://example.com/repo',
            '-revision',
            'HEAD',
            '-recipe',
            'recipe',
            '-properties',
            json.dumps(
                {
                    'buildbucket': {
                        'hostname': 'cr-buildbucket.appspot.com',
                        'build': {
                            'project':
                                'chromium',
                            'bucket':
                                'luci.chromium.try',
                            'created_by':
                                'user:john@example.com',
                            'created_ts':
                                utils.datetime_to_timestamp(build.create_time),
                            'id':
                                '1',
                            'tags': [],
                        },
                    },
                    '$recipe_engine/runtime': {
                        'is_experimental': False,
                        'is_luci': True,
                    },
                    'buildername': 'linux_chromium_rel_ng',
                    'predefined-property': 'x',
                    'predefined-property-bool': True,
                },
                sort_keys=True,
            ),
            '-logdog-project',
            'chromium',
        ],
        'secret_bytes':
            expected_secret_bytes,
        'dimensions': [
            {'key': 'cores', 'value': '8'},
            {'key': 'os', 'value': 'Ubuntu'},
            {'key': 'pool', 'value': 'Chrome'},
        ],
        'caches': [
            {'path': 'cache/a', 'name': 'a'},
            {'path': 'cache/builder', 'name': LINUX_CHROMIUM_REL_NG_CACHE_NAME},
            {'path': 'cache/git_cache', 'name': 'git_chromium'},
            {'path': 'cache/out', 'name': 'build_chromium'},
        ],
        'cipd_input': {
            'packages': [
                {
                    'package_name': 'infra/test/bar/${os_ver}',
                    'path': '.',
                    'version': 'latest',
                },
                {
                    'package_name': 'infra/test/foo/${platform}',
                    'path': 'third_party',
                    'version': 'stable',
                },
            ],
        },
    }
    # The swarming template has fallback.
    props_def_first = copy.deepcopy(props_def)
    props_def_first[u'dimensions'].append({
        u'key': u'caches',
        u'value': LINUX_CHROMIUM_REL_NG_CACHE_NAME,
    })
    props_def_first[u'dimensions'].sort(key=lambda x: (x[u'key'], x[u'value']))
    expected_task_def = {
        'name':
            'buildbucket:luci.chromium.try:linux_chromium_rel_ng-canary',
        'priority':
            '108',
        'tags': [
            'buildbucket_bucket:luci.chromium.try',
            'buildbucket_build_id:1',
            'buildbucket_hostname:cr-buildbucket.appspot.com',
            'buildbucket_template_canary:1',
            'buildbucket_template_revision:template_rev',
            'builder:linux_chromium_rel_ng',
            'buildertag:yes',
            'commontag:yes',
            (
                'log_location:logdog://luci-logdog-dev.appspot.com/chromium/'
                'buildbucket/cr-buildbucket.appspot.com/1/+/annotations'
            ),
            'luci_project:chromium',
            'recipe_name:recipe',
            'recipe_repository:https://example.com/repo',
        ],
        'pool_task_template':
            'CANARY_PREFER',
        'task_slices': [
            {
                'expiration_secs': '60',
                'properties': props_def_first,
                'wait_for_capacity': False,
            },
            {
                'expiration_secs': '3540',
                'properties': props_def,
                'wait_for_capacity': False,
            },
        ],
        'pubsub_topic':
            'projects/testbed-test/topics/swarming',
        'pubsub_userdata':
            json.dumps({
                'created_ts': utils.datetime_to_timestamp(utils.utcnow()),
                'swarming_hostname': 'chromium-swarm.appspot.com',
                'build_id': 1L,
            },
                       sort_keys=True),
        'service_account':
            'robot@example.com',
        'numerical_value_for_coverage_in_format_obj':
            42,
    }
    self.assertEqual(ununicide(actual_task_def), expected_task_def)

    self.assertEqual(
        set(build.tags), {
            'builder:linux_chromium_rel_ng',
            'swarming_dimension:cores:8',
            'swarming_dimension:os:Ubuntu',
            'swarming_dimension:pool:Chrome',
            'swarming_hostname:chromium-swarm.appspot.com',
            'swarming_tag:builder:linux_chromium_rel_ng',
            'swarming_tag:buildertag:yes',
            'swarming_tag:commontag:yes',
            'swarming_tag:priority:108',
            'swarming_tag:recipe_name:recipe',
            'swarming_tag:recipe_repository:https://example.com/repo',
            'swarming_task_id:deadbeef',
        }
    )

  def test_create_task_async_no_canary_template_explicit(self):
    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
        },
        tags=['builder:linux_chromium_rel_ng'],
        canary_preference=model.CanaryPreference.CANARY,
    )

    self.task_template_canary = None
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

  @mock.patch('swarming.swarming._should_use_canary_template', autospec=True)
  def test_create_task_async_no_canary_template_implicit(
      self, should_use_canary_template
  ):
    should_use_canary_template.return_value = True
    self.task_template_canary = None
    self.bucket_cfg.swarming.task_template_canary_percentage.value = 54

    self.json_response = {
        'task_id': 'deadbeef',
        'request': {
            'task_slices': [{
                'expiration_secs': 3600,
                'properties': {
                    'execution_timeout_secs':
                        1800,
                    'dimensions': [
                        {'key': 'cores', 'value': '8'},
                        {'key': 'os', 'value': 'Ubuntu'},
                        {'key': 'pool', 'value': 'Chrome'},
                    ],
                },
            }],
            'tags': [
                'builder:linux_chromium_rel_ng',
                'buildertag:yes',
                'commontag:yes',
                'priority:108',
                'recipe_name:recipe',
                'recipe_repository:https://example.com/repo',
            ],
        },
    }

    build = mkBuild(
        parameters={model.BUILDER_PARAMETER: 'linux_chromium_rel_ng'},
        tags=['builder:linux_chromium_rel_ng'],
        canary_preference=model.CanaryPreference.AUTO,
    )
    swarming.create_task_async(build).get_result()

    self.assertFalse(build.canary)
    should_use_canary_template.assert_called_with(54)

  def test_create_task_async_override_cfg(self):
    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
            'swarming': {
                'override_builder_cfg': {
                    # Override cores dimension.
                    'dimensions': ['cores:16'],
                    'recipe': {'name': 'bob'},
                },
            }
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    self.json_response = {
        'task_id': 'deadbeef',
        'request': {
            'task_slices': [{
                'expiration_secs': 3600,
                'properties': {
                    'execution_timeout_secs':
                        1800,
                    'dimensions': [
                        {'key': 'cores', 'value': '16'},
                        {'key': 'os', 'value': 'Ubuntu'},
                        {'key': 'pool', 'value': 'Chrome'},
                    ],
                },
            }],
            'tags': [
                'builder:linux_chromium_rel_ng',
                'buildertag:yes',
                'commontag:yes',
                'priority:108',
                'recipe_name:bob',
                'recipe_repository:https://example.com/repo',
            ],
        },
    }

    swarming.create_task_async(build).get_result()

    actual_task_def = net.json_request_async.call_args[1]['payload']
    self.assertIn(
        {'key': 'cores', 'value': '16'},
        actual_task_def['task_slices'][0]['properties']['dimensions'],
    )

  def test_create_task_async_override_cfg_malformed(self):
    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
            'swarming': {'override_builder_cfg': []},
        },
        tags=['builder:linux_chromium_rel_ng'],
    )
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
            'swarming': {'override_builder_cfg': {'name': 'x'}},
        },
        tags=['builder:linux_chromium_rel_ng'],
    )
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
            'swarming': {'override_builder_cfg': {'mixins': ['x']}},
        },
        tags=['builder:linux_chromium_rel_ng'],
    )
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
            'swarming': {'override_builder_cfg': {'blabla': 'x'}},
        },
        tags=['builder:linux_chromium_rel_ng'],
    )
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

    # Remove a required dimension.
    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
            'swarming': {'override_builder_cfg': {'dimensions': ['pool:']}},
        },
        tags=['builder:linux_chromium_rel_ng'],
    )
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

    # Override build numbers
    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
            'swarming': {'override_builder_cfg': {'build_numbers': False}},
        },
        tags=['builder:linux_chromium_rel_ng'],
    )
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

  def test_create_task_async_on_leased_build(self):
    build = mkBuild(
        parameters={model.BUILDER_PARAMETER: 'linux_chromium_rel_ng'},
        tags=['builder:linux_chromium_rel_ng'],
        lease_key=12345,
    )
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

  def test_create_task_async_without_milo_hostname(self):
    self.settings.swarming.milo_hostname = ''
    build = mkBuild(
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
            'swarming': {
                'override_builder_cfg': {
                    # Override cores dimension.
                    'dimensions': ['cores:16'],
                    'recipe': {'name': 'bob'},
                },
            },
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    self.json_response = {
        'task_id': 'deadbeef',
        'request': {
            'task_slices': [{
                'properties': {
                    'dimensions': [
                        {'key': 'cores', 'value': '16'},
                        {'key': 'os', 'value': 'Ubuntu'},
                        {'key': 'pool', 'value': 'Chrome'},
                    ],
                },
            }],
            'tags': [
                'builder:linux_chromium_rel_ng',
                'buildertag:yes',
                'commontag:yes',
                'priority:108',
                'recipe_name:bob',
                'recipe_repository:https://example.com/repo',
            ],
        },
    }

    swarming.create_task_async(build).get_result()

  def test_cancel_task(self):
    self.json_response = {'ok': True}
    swarming.cancel_task('chromium-swarm.appspot.com', 'deadbeef')
    net.json_request_async.assert_called_with(
        (
            'https://chromium-swarm.appspot.com/'
            '_ah/api/swarming/v1/task/deadbeef/cancel'
        ),
        method='POST',
        scopes=net.EMAIL_SCOPE,
        delegation_token=None,
        payload={'kill_running': True},
        deadline=None,
        max_attempts=None,
    )

  def test_cancel_running_task(self):
    self.json_response = {
        'was_running': True,
        'ok': False,
    }
    swarming.cancel_task('swarming.example.com', 'deadbeef')

  @mock.patch('swarming.swarming._load_build_run_result_async', autospec=True)
  def test_sync(self, load_build_run_result_async):
    load_build_run_result_async.return_value = future((None, None))
    cases = [
        {
            'task_result': None,
            'status': model.BuildStatus.COMPLETED,
            'result': model.BuildResult.FAILURE,
            'failure_reason': model.FailureReason.INFRA_FAILURE,
            'complete_time': utils.utcnow(),
        },
        {
            'task_result': {'state': 'PENDING'},
            'status': model.BuildStatus.SCHEDULED,
        },
        {
            'task_result': {
                'state': 'RUNNING',
                'started_ts': '2018-01-29T21:15:02.649750',
            },
            'status': model.BuildStatus.STARTED,
            'start_time': datetime.datetime(2018, 1, 29, 21, 15, 2, 649750),
        },
        {
            'task_result': {
                'state': 'COMPLETED',
                'started_ts': '2018-01-29T21:15:02.649750',
                'completed_ts': '2018-01-30T00:15:18.162860',
            },
            'build_run_result': {},
            'status': model.BuildStatus.COMPLETED,
            'result': model.BuildResult.SUCCESS,
            'start_time': datetime.datetime(2018, 1, 29, 21, 15, 2, 649750),
            'complete_time': datetime.datetime(2018, 1, 30, 0, 15, 18, 162860),
        },
        {
            'task_result': {
                'state':
                    'COMPLETED',
                'started_ts':
                    '2018-01-29T21:15:02.649750',
                'completed_ts':
                    '2018-01-30T00:15:18.162860',
                'bot_dimensions': [
                    {'key': 'os', 'value': ['Ubuntu', 'Trusty']},
                    {'key': 'pool', 'value': ['luci.chromium.try']},
                    {'key': 'id', 'value': ['bot1']},
                ],
            },
            'build_run_result': {
                'annotationUrl':
                    'logdog://logdog.example.com/chromium/prefix/+/annotations',
                'annotations':
                    json.loads(
                        json_format.MessageToJson(
                            annotations_pb2.Step(
                                substep=[
                                    annotations_pb2.Step.Substep(
                                        step=annotations_pb2.Step(
                                            name='bot_update',
                                            status=annotations_pb2.SUCCESS,
                                        ),
                                    ),
                                ],
                            )
                        )
                    ),
            },
            'status':
                model.BuildStatus.COMPLETED,
            'result':
                model.BuildResult.SUCCESS,
            'bot_dimensions': {
                'os': ['Ubuntu', 'Trusty'],
                'pool': ['luci.chromium.try'],
                'id': ['bot1'],
            },
            'start_time':
                datetime.datetime(2018, 1, 29, 21, 15, 2, 649750),
            'complete_time':
                datetime.datetime(2018, 1, 30, 0, 15, 18, 162860),
            'build_steps': [
                step_pb2.Step(name='bot_update', status=common_pb2.SUCCESS)
            ],
        },
        {
            'task_result': {
                'state': 'COMPLETED',
                'failure': True,
                'started_ts': '2018-01-29T21:15:02.649750',
                'completed_ts': '2018-01-30T00:15:18.162860',
            },
            'build_run_result': {},
            'status': model.BuildStatus.COMPLETED,
            'result': model.BuildResult.FAILURE,
            'failure_reason': model.FailureReason.BUILD_FAILURE,
            'start_time': datetime.datetime(2018, 1, 29, 21, 15, 2, 649750),
            'complete_time': datetime.datetime(2018, 1, 30, 0, 15, 18, 162860),
        },
        {
            'task_result': {
                'state': 'COMPLETED',
                'failure': True,
                'started_ts': '2018-01-29T21:15:02.649750',
                'completed_ts': '2018-01-30T00:15:18.162860',
            },
            'build_run_result': {
                'infraFailure': {
                    'type': 'BOOTSTRAPPER_ERROR',
                    'text': 'it is not good',
                },
            },
            'status': model.BuildStatus.COMPLETED,
            'result': model.BuildResult.FAILURE,
            'failure_reason': model.FailureReason.INFRA_FAILURE,
            'start_time': datetime.datetime(2018, 1, 29, 21, 15, 2, 649750),
            'complete_time': datetime.datetime(2018, 1, 30, 0, 15, 18, 162860),
        },
        {
            'task_result': {
                'state': 'COMPLETED',
                'failure': True,
                'started_ts': '2018-01-29T21:15:02.649750',
                'completed_ts': '2018-01-30T00:15:18.162860',
            },
            'build_run_result': None,
            'status': model.BuildStatus.COMPLETED,
            'result': model.BuildResult.FAILURE,
            'failure_reason': model.FailureReason.INFRA_FAILURE,
            'start_time': datetime.datetime(2018, 1, 29, 21, 15, 2, 649750),
            'complete_time': datetime.datetime(2018, 1, 30, 0, 15, 18, 162860),
        },
        {
            'task_result': {
                'state': 'COMPLETED',
                'failure': True,
                'started_ts': '2018-01-29T21:15:02.649750',
                'completed_ts': '2018-01-30T00:15:18.162860',
            },
            'build_run_result_error': swarming._BUILD_RUN_RESULT_CORRUPTED,
            'status': model.BuildStatus.COMPLETED,
            'result': model.BuildResult.FAILURE,
            'failure_reason': model.FailureReason.INFRA_FAILURE,
            'start_time': datetime.datetime(2018, 1, 29, 21, 15, 2, 649750),
            'complete_time': datetime.datetime(2018, 1, 30, 0, 15, 18, 162860),
        },
        {
            'task_result': {
                'state': 'COMPLETED',
                'failure': True,
                'internal_failure': True,
                'started_ts': '2018-01-29T21:15:02.649750',
                'completed_ts': '2018-01-30T00:15:18.162860',
            },
            'status': model.BuildStatus.COMPLETED,
            'result': model.BuildResult.FAILURE,
            'failure_reason': model.FailureReason.INFRA_FAILURE,
            'start_time': datetime.datetime(2018, 1, 29, 21, 15, 2, 649750),
            'complete_time': datetime.datetime(2018, 1, 30, 0, 15, 18, 162860),
        },
        {
            'task_result': {
                'state': 'BOT_DIED',
                'started_ts': '2018-01-29T21:15:02.649750',
                'abandoned_ts': '2018-01-30T00:15:18.162860',
            },
            'status': model.BuildStatus.COMPLETED,
            'result': model.BuildResult.FAILURE,
            'failure_reason': model.FailureReason.INFRA_FAILURE,
            'start_time': datetime.datetime(2018, 1, 29, 21, 15, 2, 649750),
            'complete_time': datetime.datetime(2018, 1, 30, 0, 15, 18, 162860),
        },
        {
            'task_result': {
                'state': 'TIMED_OUT',
                'started_ts': '2018-01-29T21:15:02.649750',
                'completed_ts': '2018-01-30T00:15:18.162860',
            },
            'status': model.BuildStatus.COMPLETED,
            'result': model.BuildResult.FAILURE,
            'failure_reason': model.FailureReason.INFRA_FAILURE,
            'start_time': datetime.datetime(2018, 1, 29, 21, 15, 2, 649750),
            'complete_time': datetime.datetime(2018, 1, 30, 0, 15, 18, 162860),
        },
        {
            'task_result': {
                'state': 'EXPIRED',
                'abandoned_ts': '2018-01-30T00:15:18.162860',
            },
            'status': model.BuildStatus.COMPLETED,
            'result': model.BuildResult.CANCELED,
            'cancelation_reason': model.CancelationReason.TIMEOUT,
            'complete_time': datetime.datetime(2018, 1, 30, 0, 15, 18, 162860),
        },
        {
            'task_result': {
                'state': 'KILLED',
                'abandoned_ts': '2018-01-30T00:15:18.162860',
            },
            'status': model.BuildStatus.COMPLETED,
            'result': model.BuildResult.CANCELED,
            'cancelation_reason': model.CancelationReason.CANCELED_EXPLICITLY,
            'complete_time': datetime.datetime(2018, 1, 30, 0, 15, 18, 162860),
        },
        {
            'task_result': {
                'state': 'CANCELED',
                'abandoned_ts': '2018-01-30T00:15:18.162860',
            },
            'status': model.BuildStatus.COMPLETED,
            'result': model.BuildResult.CANCELED,
            'cancelation_reason': model.CancelationReason.CANCELED_EXPLICITLY,
            'complete_time': datetime.datetime(2018, 1, 30, 0, 15, 18, 162860),
        },
        {
            'task_result': {
                'state': 'NO_RESOURCE',
                'abandoned_ts': '2018-01-30T00:15:18.162860',
            },
            'status': model.BuildStatus.COMPLETED,
            'result': model.BuildResult.CANCELED,
            'cancelation_reason': model.CancelationReason.TIMEOUT,
            'complete_time': datetime.datetime(2018, 1, 30, 0, 15, 18, 162860),
        },
    ]

    for case in cases:
      build = mkBuild(canary=False)
      build.put()
      steps_key = model.BuildSteps.key_for(build.key)

      # This is cleanup after prev test in this func.
      # TODO(nodir): split the test.
      steps_key.delete()

      load_build_run_result_async.return_value = future((
          case.get('build_run_result'),
          case.get('build_run_result_error', None),
      ))
      swarming._sync_build_async(
          1, case['task_result'], 'luci.chromium.ci', 'linux-rel'
      ).get_result()

      build = build.key.get()
      self.assertEqual(build.status, case['status'])
      self.assertEqual(build.result, case.get('result'))
      self.assertEqual(build.failure_reason, case.get('failure_reason'))
      self.assertEqual(build.cancelation_reason, case.get('cancelation_reason'))
      self.assertEqual(build.start_time, case.get('start_time'))
      self.assertEqual(build.complete_time, case.get('complete_time'))
      self.assertEqual(
          build.result_details.get('swarming', {}).get('bot_dimensions'),
          case.get('bot_dimensions', {})
      )

      expected_steps = case.get('build_steps') or []
      actual_build_steps = steps_key.get()
      self.assertTrue(
          build.status != model.BuildStatus.COMPLETED or
          actual_build_steps is not None
      )
      step_container = build_pb2.Build()
      if actual_build_steps:
        step_container = actual_build_steps.step_container
      self.assertEqual(list(step_container.steps), expected_steps)

  @mock.patch('swarming.isolate.fetch_async')
  def test_load_build_run_result_async(self, fetch_isolate_async):
    self.assertEqual(
        swarming._load_build_run_result_async({}, 'luci.chromium.ci',
                                              'linux-rel').get_result(),
        (None, None),
    )

    expected = {
        'infra_failure': {'text': 'not good'},
    }
    fetch_isolate_async.side_effect = [
        # isolated
        future(
            json.dumps({
                'files': {
                    swarming._BUILD_RUN_RESULT_FILENAME: {
                        'h': 'deadbeef',
                        's': 2048,
                    },
                },
            })
        ),
        # build-run-result.json
        future(json.dumps(expected)),
    ]
    actual, error = swarming._load_build_run_result_async({
        'id': 'taskid',
        'outputs_ref': {
            'isolatedserver': 'https://isolate.example.com',
            'namespace': 'default-gzip',
            'isolated': 'badcoffee',
        },
    }, 'luci.chromium.ci', 'linux-rel').get_result()
    self.assertIsNone(error)
    self.assertEqual(expected, actual)
    fetch_isolate_async.assert_any_call(
        isolate.Location(
            'isolate.example.com',
            'default-gzip',
            'badcoffee',
        )
    )
    fetch_isolate_async.assert_any_call(
        isolate.Location(
            'isolate.example.com',
            'default-gzip',
            'deadbeef',
        )
    )

  @mock.patch('swarming.isolate.fetch_async')
  def test_load_build_run_result_async_too_large(self, fetch_isolate_async):
    fetch_isolate_async.return_value = future(
        json.dumps({
            'files': {
                swarming._BUILD_RUN_RESULT_FILENAME: {
                    'h': 'deadbeef',
                    's': 1 + (1 << 20),
                },
            },
        })
    )
    actual, error = swarming._load_build_run_result_async({
        'id': 'taskid',
        'outputs_ref': {
            'isolatedserver': 'https://isolate.example.com',
            'namespace': 'default-gzip',
            'isolated': 'badcoffee',
        },
    }, 'luci.chromium.ci', 'linux-rel').get_result()
    self.assertEqual(error, swarming._BUILD_RUN_RESULT_TOO_LARGE)
    self.assertIsNone(actual)

  @mock.patch('swarming.isolate.fetch_async')
  def test_load_build_run_result_async_no_result(self, fetch_isolate_async):
    # isolated only, without the result
    fetch_isolate_async.return_value = future(
        json.dumps({
            'files': {'soemthing_else.txt': {
                'h': 'deadbeef',
                's': 2048,
            }},
        })
    )
    actual, error = swarming._load_build_run_result_async({
        'id': 'taskid',
        'outputs_ref': {
            'isolatedserver': 'https://isolate.example.com',
            'namespace': 'default-gzip',
            'isolated': 'badcoffee',
        },
    }, 'luci.chromium.ci', 'linux-rel').get_result()
    self.assertIsNone(error)
    self.assertIsNone(actual)

  def test_load_build_run_result_async_non_https_server(self):
    run_result, error = swarming._load_build_run_result_async({
        'id': 'taskid',
        'outputs_ref': {
            'isolatedserver': 'http://isolate.example.com',
            'namespace': 'default-gzip',
            'isolated': 'badcoffee',
        },
    }, 'luci.chromium.ci', 'linux-rel').get_result()
    self.assertEqual(error, swarming._BUILD_RUN_RESULT_CORRUPTED)
    self.assertIsNone(run_result)

  @mock.patch('swarming.isolate.fetch_async')
  def test_load_build_run_result_invalid_json(self, fetch_isolate_async):
    fetch_isolate_async.return_value = future('{"incomplete_json')
    run_result, error = swarming._load_build_run_result_async({
        'id': 'taskid',
        'outputs_ref': {
            'isolatedserver': 'https://isolate.example.com',
            'namespace': 'default-gzip',
            'isolated': 'badcoffee',
        },
    }, 'luci.chromium.ci', 'linux-rel').get_result()
    self.assertEqual(error, swarming._BUILD_RUN_RESULT_CORRUPTED)
    self.assertIsNone(run_result)

  @mock.patch('swarming.isolate.fetch_async')
  def test_load_build_run_result_async_isolate_error(self, fetch_isolate_async):
    fetch_isolate_async.side_effect = isolate.Error()
    with self.assertRaises(isolate.Error):
      swarming._load_build_run_result_async({
          'id': 'taskid',
          'outputs_ref': {
              'isolatedserver': 'https://isolate.example.com',
              'namespace': 'default-gzip',
              'isolated': 'badcoffee',
          },
      }, 'luci.chromium.ci', 'linux-rel').get_result()

  def test_generate_build_url(self):
    build = mkBuild(
        parameters={model.BUILDER_PARAMETER: 'linux_chromium_rel_ng'},
        swarming_hostname='swarming.example.com',
        swarming_task_id='deadbeef',
    )

    self.assertEqual(
        swarming._generate_build_url('milo.example.com', build, 3), (
            'https://milo.example.com/p/chromium/builders/'
            'luci.chromium.try/linux_chromium_rel_ng/3'
        )
    )

    self.assertEqual(
        swarming._generate_build_url('milo.example.com', build, None),
        ('https://milo.example.com/p/chromium/builds/b1')
    )

    self.assertEqual(
        swarming._generate_build_url(None, build, 54),
        ('https://swarming.example.com/task?id=deadbeef')
    )

  def test_extract_properties(self):
    self.assertEqual(
        swarming._extract_properties({
            'substep': [
                {
                    'step': {
                        'property': [
                            {'name': 'p1', 'value': '{}'},
                            {'name': 'p2', 'value': '"s"'},
                        ]
                    }
                },
                {},
                {'step': {}},
                {
                    'step': {
                        'property': [
                            {'name': 'p2', 'value': '"s2"'},
                            {'name': 'p3', 'value': '2'},
                        ]
                    }
                },
            ],
        }),
        {
            'p1': {},
            'p2': 's2',
            'p3': 2,
        },
    )


class SubNotifyTest(BaseTest):

  def setUp(self):
    super(SubNotifyTest, self).setUp()
    self.handler = swarming.SubNotify(response=webapp2.Response())

    self.patch(
        'swarming.swarming._load_build_run_result_async',
        autospec=True,
        return_value=future(({}, False)),
    )

  def test_unpack_msg(self):
    self.assertEqual(
        self.handler.unpack_msg({
            'messageId':
                '1',
            'data':
                b64json({
                    'task_id':
                        'deadbeef',
                    'userdata':
                        json.dumps({
                            'created_ts': 1448841600000000,
                            'swarming_hostname': 'chromium-swarm.appspot.com',
                            'build_id': 1L,
                        })
                })
        }), (
            'chromium-swarm.appspot.com', datetime.datetime(2015, 11, 30),
            'deadbeef', 1
        )
    )

  def test_unpack_msg_with_err(self):
    with self.assert_bad_message():
      self.handler.unpack_msg({})
    with self.assert_bad_message():
      self.handler.unpack_msg({'data': b64json([])})

    bad_data = [
        # Bad task id.
        {
            'userdata':
                json.dumps({
                    'created_ts': 1448841600000,
                    'swarming_hostname': 'chromium-swarm.appspot.com',
                })
        },

        # Bad swarming hostname.
        {
            'task_id': 'deadbeef',
        },
        {
            'task_id': 'deadbeef',
            'userdata': '{}',
        },
        {
            'task_id': 'deadbeef',
            'userdata': json.dumps({
                'swarming_hostname': 1,
            }),
        },

        # Bad creation time
        {
            'task_id':
                'deadbeef',
            'userdata':
                json.dumps({
                    'swarming_hostname': 'chromium-swarm.appspot.com',
                }),
        },
        {
            'task_id':
                'deadbeef',
            'userdata':
                json.dumps({
                    'created_ts': 'foo',
                    'swarming_hostname': 'chromium-swarm.appspot.com',
                }),
        },
    ]

    for data in bad_data:
      with self.assert_bad_message():
        self.handler.unpack_msg({'data': b64json(data)})

  @mock.patch('swarming.swarming._load_task_result_async', autospec=True)
  def test_post(self, load_task_result_async):
    build = mkBuild(
        parameters={model.BUILDER_PARAMETER: 'release'},
        tags=['builder:linux_chromium_rel_ng'],
        swarming_hostname='chromium-swarm.appspot.com',
        swarming_task_id='deadbeef',
        canary=False,
    )
    build.put()

    self.handler.request = mock.Mock(
        json={
            'message': {
                'messageId':
                    '1',
                'data':
                    b64json({
                        'task_id':
                            'deadbeef',
                        'userdata':
                            json.dumps({
                                'build_id':
                                    1L,
                                'created_ts':
                                    1448841600000000,
                                'swarming_hostname':
                                    'chromium-swarm.appspot.com',
                            }),
                    }),
            }
        }
    )
    load_task_result_async.return_value = future({
        'task_id': 'deadbeef',
        'state': 'COMPLETED',
    })

    self.handler.post()

    build = build.key.get()
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(build.result, model.BuildResult.SUCCESS)

  def test_post_with_different_swarming_hostname(self):
    build = mkBuild(
        parameters={model.BUILDER_PARAMETER: 'release'},
        tags=['builder:linux_chromium_rel_ng'],
        swarming_hostname='chromium-swarm.appspot.com',
        swarming_task_id='deadbeef',
    )
    build.put()

    self.handler.request = mock.Mock(
        json={
            'message': {
                'messageId':
                    '1',
                'data':
                    b64json({
                        'task_id':
                            'deadbeef',
                        'userdata':
                            json.dumps({
                                'build_id':
                                    1L,
                                'created_ts':
                                    1448841600000000,
                                'swarming_hostname':
                                    'chromium-swarm.appspot.com.au',
                            }),
                    }),
            }
        }
    )

    with self.assert_bad_message(expect_redelivery=False):
      self.handler.post()

  def test_post_with_different_task_id(self):
    build = mkBuild(
        parameters={model.BUILDER_PARAMETER: 'release'},
        tags=['builder:release'],
        swarming_hostname='chromium-swarm.appspot.com',
        swarming_task_id='deadbeef',
    )
    build.put()

    self.handler.request = mock.Mock(
        json={
            'message': {
                'messageId':
                    '1',
                'data':
                    b64json({
                        'task_id':
                            'deadbeefffffffffff', 'userdata':
                                json.dumps({
                                    'build_id':
                                        1L,
                                    'created_ts':
                                        1448841600000000,
                                    'swarming_hostname':
                                        'chromium-swarm.appspot.com',
                                })
                    }),
            }
        }
    )

    with self.assert_bad_message(expect_redelivery=False):
      self.handler.post()

  def test_post_without_task_id(self):
    self.handler.request = mock.Mock(
        json={
            'message': {
                'messageId':
                    '1',
                'data':
                    b64json({
                        'userdata':
                            json.dumps({
                                'build_id':
                                    1L,
                                'created_ts':
                                    1448841600000000,
                                'swarming_hostname':
                                    'chromium-swarm.appspot.com',
                            })
                    }),
            }
        }
    )
    with self.assert_bad_message(expect_redelivery=False):
      self.handler.post()

  def test_post_without_build_id(self):
    self.handler.request = mock.Mock(
        json={
            'message': {
                'messageId':
                    '1',
                'data':
                    b64json({
                        'task_id':
                            'deadbeef',
                        'userdata':
                            json.dumps({
                                'created_ts':
                                    1448841600000000,
                                'swarming_hostname':
                                    'chromium-swarm.appspot.com',
                            }),
                    }),
            }
        }
    )
    with self.assert_bad_message(expect_redelivery=False):
      self.handler.post()

  def test_post_without_build(self):
    userdata = {
        'created_ts': 1448841600000000,
        'swarming_hostname': 'chromium-swarm.appspot.com',
        'build_id': 1L,
    }
    msg_data = {
        'task_id': 'deadbeef',
        'userdata': json.dumps(userdata),
    }
    self.handler.request = mock.Mock(
        json={
            'message': {
                'messageId': '1',
                'data': b64json(msg_data),
            },
        }
    )

    with self.assert_bad_message(expect_redelivery=True):
      self.handler.post()

    userdata['created_ts'] = 1438841600000000
    msg_data['userdata'] = json.dumps(userdata)
    self.handler.request.json['message']['data'] = b64json(msg_data)
    with self.assert_bad_message(expect_redelivery=False):
      self.handler.post()

  @contextlib.contextmanager
  def assert_bad_message(self, expect_redelivery=False):
    self.handler.bad_message = False
    err = exc.HTTPClientError if expect_redelivery else exc.HTTPOk
    with self.assertRaises(err):
      yield
    self.assertTrue(self.handler.bad_message)

  @mock.patch('swarming.swarming.SubNotify._process_msg', autospec=True)
  def test_dedup_messages(self, _process_msg):
    self.handler.request = mock.Mock(
        json={'message': {
            'messageId': '1',
            'data': b64json({}),
        }}
    )

    self.handler.post()
    self.handler.post()

    self.assertEquals(_process_msg.call_count, 1)


class CronUpdateTest(BaseTest):

  def setUp(self):
    super(CronUpdateTest, self).setUp()
    self.build = mkBuild(
        start_time=self.now + datetime.timedelta(seconds=1),
        parameters={
            model.BUILDER_PARAMETER: 'release',
        },
        tags=['builder:release'],
        swarming_hostname='chromium-swarm.appsot.com',
        swarming_task_id='deadeef',
        status=model.BuildStatus.STARTED,
        lease_key=123,
        lease_expiration_date=self.now + datetime.timedelta(minutes=5),
        leasee=auth.Anonymous,
        canary=False,
    )
    self.build.put()
    self.now += datetime.timedelta(minutes=5)

    self.patch(
        'swarming.swarming._load_build_run_result_async',
        autospec=True,
        return_value=future(({}, False)),
    )

  @mock.patch('swarming.swarming._load_task_result_async', autospec=True)
  def test_sync_build_async(self, load_task_result_async):
    load_task_result_async.return_value = future({
        'state': 'RUNNING',
    })

    build = self.build
    swarming.CronUpdateBuilds().update_build_async(build).get_result()
    build = build.key.get()
    self.assertEqual(build.status, model.BuildStatus.STARTED)
    self.assertIsNotNone(build.lease_key)
    self.assertIsNone(build.complete_time)
    self.assertIsNotNone(build.result_details)

    load_task_result_async.return_value = future({
        'state': 'COMPLETED',
    })

    swarming.CronUpdateBuilds().update_build_async(build).get_result()
    build = build.key.get()
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(build.result, model.BuildResult.SUCCESS)
    self.assertIsNone(build.lease_key)
    self.assertIsNotNone(build.complete_time)
    self.assertIsNotNone(build.result_details)

  @mock.patch('swarming.swarming._load_task_result_async', autospec=True)
  def test_sync_build_async_no_task(self, load_task_result_async):
    load_task_result_async.return_value = future(None)

    build = self.build
    swarming.CronUpdateBuilds().update_build_async(build).get_result()
    build = build.key.get()
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(build.result, model.BuildResult.FAILURE)
    self.assertEqual(build.failure_reason, model.FailureReason.INFRA_FAILURE)
    self.assertIsNotNone(build.result_details)
    self.assertIsNone(build.lease_key)
    self.assertIsNotNone(build.complete_time)


class TestApplyIfTags(BaseTest):

  def test_no_replacement(self):
    obj = {
        'tags': [
            'something',
            'other_thing',
        ],
        'some key': ['value', {'other_key': 100}],
        'some other key': {
            'a': 'b',
            'b': 'c',
        },
    }
    self.assertEqual(swarming._apply_if_tags(obj), obj)

  def test_drop_if_tag(self):
    obj = {
        'tags': [
            'something',
            'other_thing',
        ],
        'some key': ['value', {
            'other_key': 100,
            '#if-tag': 'something',
        }],
        'some other key': {
            'a': 'b',
            'b': 'c',
        },
    }
    self.assertEqual(
        swarming._apply_if_tags(obj), {
            'tags': [
                'something',
                'other_thing',
            ],
            'some key': ['value', {
                'other_key': 100,
            }],
            'some other key': {
                'a': 'b',
                'b': 'c',
            },
        }
    )

  def test_drop_clause(self):
    obj = {
        'tags': [
            'something',
            'other_thing',
        ],
        'some key': ['value', {
            'other_key': 100,
            '#if-tag': 'something',
        }],
        'some other key': {
            'a': 'b',
            'b': 'c',
            '#if-tag': 'nope',
        },
    }
    self.assertEqual(
        swarming._apply_if_tags(obj), {
            'tags': [
                'something',
                'other_thing',
            ],
            'some key': ['value', {
                'other_key': 100,
            }],
        }
    )

  def test_parse_ts_without_usecs(self):
    actual = swarming._parse_ts('2018-02-23T04:22:45')
    expected = datetime.datetime(2018, 2, 23, 4, 22, 45)
    self.assertEqual(actual, expected)


def b64json(data):
  return base64.b64encode(json.dumps(data))


def mkBuild(**kwargs):
  args = dict(
      id=1,
      project='chromium',
      bucket='luci.chromium.try',
      create_time=utils.utcnow(),
      created_by=auth.Identity('user', 'john@example.com'),
      canary_preference=model.CanaryPreference.PROD,
      parameters={},
  )
  args.update(kwargs)
  return model.Build(**args)
