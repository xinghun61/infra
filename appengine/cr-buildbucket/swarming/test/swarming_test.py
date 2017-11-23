# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import collections
import contextlib
import datetime
import json
import logging

from components import utils
utils.fix_protobuf_package()

from google import protobuf
from google.appengine.ext import ndb

from components import auth
from components import net
from components import utils
from testing_utils import testing
from webob import exc
import mock
import webapp2

from swarming import isolate
from swarming import swarming
from proto import project_config_pb2
from proto import service_config_pb2
from test.test_util import future, ununicide
import errors
import model


LINUX_CHROMIUM_REL_NG_CACHE_NAME = (
    'builder_980988014eb33bf5578a0f44e123402888e39083523bfd9214fea0c8a080db17')


class BaseTest(testing.AppengineTestCase):
  def setUp(self):
    super(BaseTest, self).setUp()

    self.patch(
        'events.enqueue_tasks_async', autospec=True, return_value=future(None))

    self.now = datetime.datetime(2015, 11, 30)
    self.patch(
        'components.utils.utcnow', autospec=True,
        side_effect=lambda: self.now)


class SwarmingTest(BaseTest):
  def setUp(self):
    super(SwarmingTest, self).setUp()

    self.json_response = None
    self.net_err_response = None
    def json_request_async(*_, **__):
      if self.net_err_response is not None:
        f = ndb.Future()
        f.set_exception(self.net_err_response)
        return f
      if self.json_response is not None:
        return future(self.json_response)
      self.fail('unexpected outbound request')  # pragma: no cover

    self.patch(
        'components.net.json_request_async', autospec=True,
        side_effect=json_request_async)

    self.settings = service_config_pb2.SwarmingSettings(
        default_hostname='swarming.example.com',
        milo_hostname='milo.example.com',
    )
    self.patch(
        'swarming.swarming.get_settings_async', autospec=True,
        return_value=future(self.settings))

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
          build_numbers: true
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
      }
    '''
    self.bucket_cfg = project_config_pb2.Bucket()
    protobuf.text_format.Merge(bucket_cfg_text, self.bucket_cfg)

    self.patch(
        'config.get_bucket_async', autospec=True,
        return_value=future(('chromium', self.bucket_cfg)))

    self.task_template = {
      'name': 'buildbucket:${bucket}:${builder}',
      'priority': '100',
      'expiration_secs': '3600',
      'tags': [
        ('log_location:logdog://luci-logdog-dev.appspot.com/${project}/'
         'buildbucket/${hostname}/${build_id}/+/annotations'),
        'luci_project:${project}',
      ],
      'properties': {
        'execution_timeout_secs': '3600',
        'extra_args': [
          'cook',
          '-repository', '${repository}',
          '-revision', '${revision}',
          '-recipe', '${recipe}',
          '-properties', '${properties_json}',
          '-logdog-project', '${project}',
        ],
        'caches': [
          {'path': '${cache_dir}/builder', 'name': 'builder_${builder_hash}'},
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
      },
      'numerical_value_for_coverage_in_format_obj': 42,
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
          'template_rev',
          json.dumps(template) if template is not None else None
      ))

    self.patch(
        'components.config.get_self_config_async',
        side_effect=get_self_config_async)

    self.patch(
        'components.auth.delegate_async', return_value=future('blah'))
    self.patch(
        'google.appengine.api.app_identity.get_default_version_hostname',
        return_value='cr-buildbucket.appspot.com')

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
      p['builder_name'] = 'foo'
      with self.assertRaises(errors.InvalidInputError):
        swarming.validate_build_parameters(p['builder_name'], p)

    swarming.validate_build_parameters('foo', {
      'builder_name': 'foo',
      'properties': {
        'blamelist': ['a@example.com'],
      },
      'changes': [{'author': {'email': 'a@example.com'}}],
    })

  def test_shared_cache(self):
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.caches.add(
        path='builder',
        name='shared_builder_cache'
    )

    build = mkBuild(
        parameters={
          'builder_name': 'linux_chromium_rel_ng',
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    task_def = swarming.prepare_task_def_async(
        build, self.settings).get_result()

    self.assertEqual(task_def['properties']['caches'], [
      {'path': 'cache/a', 'name': 'a'},
      {'path': 'cache/builder', 'name': 'shared_builder_cache'},
      {'path': 'cache/git_cache', 'name': 'git_chromium'},
      {'path': 'cache/out', 'name': 'build_chromium'},
    ])

  def test_execution_timeout(self):
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.execution_timeout_secs = 120

    build = mkBuild(
        parameters={
          'builder_name': 'linux_chromium_rel_ng',
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    task_def = swarming.prepare_task_def_async(
        build, self.settings).get_result()

    self.assertEqual(
        task_def['properties']['execution_timeout_secs'], '120')

    builder_cfg.execution_timeout_secs = 60
    task_def = swarming.prepare_task_def_async(
        build, self.settings).get_result()
    self.assertEqual(
        task_def['properties']['execution_timeout_secs'], '60')

  def test_auto_builder_dimension(self):
    builder_cfg = self.bucket_cfg.swarming.builders[0]
    builder_cfg.auto_builder_dimension.value = True

    build = mkBuild(
        parameters={
          'builder_name': 'linux_chromium_rel_ng',
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    task_def = swarming.prepare_task_def_async(
        build, self.settings).get_result()
    self.assertEqual(task_def['properties']['dimensions'], sorted([
      {'key': 'builder', 'value': 'linux_chromium_rel_ng'},
      {'key': 'cores', 'value': '8'},
      {'key': 'os', 'value': 'Ubuntu'},
      {'key': 'pool', 'value': 'Chrome'},
    ]))

    # But don't override if "builder" dimension is already set.
    builder_cfg.dimensions.append('builder:custom')
    task_def = swarming.prepare_task_def_async(
        build, self.settings).get_result()
    self.assertEqual(task_def['properties']['dimensions'], sorted([
      {'key': 'builder', 'value': 'custom'},
      {'key': 'cores', 'value': '8'},
      {'key': 'os', 'value': 'Ubuntu'},
      {'key': 'pool', 'value': 'Chrome'},
    ]))

  def test_is_migrating_builder_prod_async(self):
    build = mkBuild(parameters={'properties': {}})
    builder_cfg = self.bucket_cfg.swarming.builders[0]

    def is_prod():
      return swarming._is_migrating_builder_prod_async(
          builder_cfg, build).get_result()

    self.assertIsNone(is_prod())
    self.assertFalse(net.json_request_async.called)

    builder_cfg.luci_migration_host.value = 'migration.example.com'
    self.assertIsNone(is_prod())
    self.assertFalse(net.json_request_async.called)

    self.json_response = {'luci_is_prod': True, 'bucket': 'luci.chromium.try'}
    build.parameters['properties']['mastername'] = 'tryserver.chromium.linux'
    self.assertTrue(is_prod())
    self.assertTrue(net.json_request_async.called)
    net.json_request_async.reset_mock()

    self.json_response['luci_is_prod'] = False
    self.assertFalse((is_prod()))
    self.assertTrue(net.json_request_async.called)

    self.net_err_response = net.NotFoundError('nope', 404, "can't find it")
    self.assertIsNone(is_prod())

    self.net_err_response = net.Error('BOOM', 500, "IT'S BAD")
    self.assertIsNone(is_prod())

    self.net_err_response = None
    self.json_response = {'foo': True}
    self.assertIsNone(is_prod())

  def test_create_task_async(self):
    self.patch(
        'components.auth.get_current_identity', autospec=True,
        return_value=auth.Identity('user', 'john@example.com'))
    self.patch(
        'swarming.swarming._is_migrating_builder_prod_async',
        autospec=True, return_value=future(True))

    build = mkBuild(
        parameters={
          'builder_name': 'linux_chromium_rel_ng',
          'properties': {
            'a': 'b',
          },
          'changes': [{
            'author': {'email': 'bob@example.com'},
            'repo_url': 'https://chromium.googlesource.com/chromium/src',
          }]
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    self.json_response = {
      'task_id': 'deadbeef',
      'request': {
        'properties': {
          'dimensions': [
            {'key': 'cores', 'value': '8'},
            {'key': 'os', 'value': 'Ubuntu'},
            {'key': 'pool', 'value': 'Chrome'},
          ],
        },
        'tags': [
          'build_address:luci.chromium.try/linux_chromium_rel_ng/1',
          'builder:linux_chromium_rel_ng',
          'buildertag:yes',
          'commontag:yes',
          'priority:108',
          'recipe_name:recipe',
          'recipe_repository:https://example.com/repo',
          'recipe_revision:HEAD',
        ]
      }
    }

    swarming.create_task_async(build).get_result()

    # Test swarming request.
    self.assertEqual(
        net.json_request_async.call_args[0][0],
        'https://chromium-swarm.appspot.com/_ah/api/swarming/v1/tasks/new')
    actual_task_def = net.json_request_async.call_args[1]['payload']
    expected_task_def = {
      'name': 'buildbucket:luci.chromium.try:linux_chromium_rel_ng',
      'priority': '108',
      'expiration_secs': '3600',
      'tags': [
        'build_address:luci.chromium.try/linux_chromium_rel_ng/1',
        'buildbucket_bucket:luci.chromium.try',
        'buildbucket_build_id:1',
        'buildbucket_hostname:cr-buildbucket.appspot.com',
        'buildbucket_template_revision:template_rev',
        'builder:linux_chromium_rel_ng',
        'buildertag:yes',
        'commontag:yes',
        ('log_location:logdog://luci-logdog-dev.appspot.com/chromium/'
         'buildbucket/cr-buildbucket.appspot.com/1/+/annotations'),
        'luci_project:chromium',
        'recipe_name:recipe',
        'recipe_repository:https://example.com/repo',
        'recipe_revision:HEAD',
      ],
      'properties': {
        'execution_timeout_secs': '3600',
        'extra_args': [
          'cook',
          '-repository', 'https://example.com/repo',
          '-revision', 'HEAD',
          '-recipe', 'recipe',
          '-properties', json.dumps({
            'a': 'b',
            'blamelist': ['bob@example.com'],
            'buildbucket': {
              'hostname': 'cr-buildbucket.appspot.com',
              'build': {
                'bucket': 'luci.chromium.try',
                'created_by': 'user:john@example.com',
                'created_ts': utils.datetime_to_timestamp(build.create_time),
                'id': '1',
                'tags': [],
              },
            },
            'build_id': 'buildbucket/cr-buildbucket.appspot.com/1',
            'buildername': 'linux_chromium_rel_ng',
            'buildnumber': 1,
            'predefined-property': 'x',
            'predefined-property-bool': True,
            'repository': 'https://chromium.googlesource.com/chromium/src',
            '$recipe_engine/runtime': {
              'is_experimental': False,
              'is_luci': True,
            },
          }, sort_keys=True),
          '-logdog-project', 'chromium',
        ],
        'dimensions': sorted([
          {'key': 'cores', 'value': '8'},
          {'key': 'os', 'value': 'Ubuntu'},
          {'key': 'pool', 'value': 'Chrome'},
        ]),
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
      },
      'pubsub_topic': 'projects/testbed-test/topics/swarming',
      'pubsub_userdata': json.dumps({
        'created_ts': utils.datetime_to_timestamp(utils.utcnow()),
        'swarming_hostname': 'chromium-swarm.appspot.com',
        'build_id': 1L,
      }, sort_keys=True),
      'service_account': 'robot@example.com',
      'numerical_value_for_coverage_in_format_obj': 42,
    }
    self.assertEqual(ununicide(actual_task_def), expected_task_def)

    self.assertEqual(set(build.tags), {
      'build_address:luci.chromium.try/linux_chromium_rel_ng/1',
      'builder:linux_chromium_rel_ng',
      'swarming_dimension:cores:8',
      'swarming_dimension:os:Ubuntu',
      'swarming_dimension:pool:Chrome',
      'swarming_hostname:chromium-swarm.appspot.com',
      'swarming_tag:build_address:luci.chromium.try/linux_chromium_rel_ng/1',
      'swarming_tag:builder:linux_chromium_rel_ng',
      'swarming_tag:buildertag:yes',
      'swarming_tag:commontag:yes',
      'swarming_tag:priority:108',
      'swarming_tag:recipe_name:recipe',
      'swarming_tag:recipe_repository:https://example.com/repo',
      'swarming_tag:recipe_revision:HEAD',
      'swarming_task_id:deadbeef',
    })
    self.assertEqual(
        build.url,
        ('https://milo.example.com'
         '/p/chromium/builders/luci.chromium.try/linux_chromium_rel_ng/1'))

    # Test delegation token params.
    self.assertEqual(auth.delegate_async.mock_calls, [mock.call(
        services=[u'https://chromium-swarm.appspot.com'],
        audience=[auth.Identity('user', 'test@localhost')],
        impersonate=auth.Identity('user', 'john@example.com'),
        tags=['buildbucket:bucket:luci.chromium.try'],
    )])

  def test_create_task_async_for_non_swarming_bucket(self):
    self.bucket_cfg.ClearField('swarming')
    build = mkBuild(
        parameters={'builder_name': 'linux_chromium_rel_ng'},
        tags=['builder:linux_chromium_rel_ng'],
    )

    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

  def test_create_task_async_without_template(self):
    self.task_template = None
    self.task_template_canary = None

    build = mkBuild(
        parameters={'builder_name': 'linux_chromium_rel_ng'},
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
        'builder_name': 'non-existent builder',
      }
      swarming.create_task_async(build).get_result()

    with self.assertRaises(errors.InvalidInputError):
      build.parameters['builder_name'] = 2
      swarming.create_task_async(build).get_result()

  def test_create_task_async_canary_template(self):
    build = mkBuild(
        parameters={
          'builder_name': 'linux_chromium_rel_ng',
        },
        tags=['builder:linux_chromium_rel_ng'],
        canary_preference=model.CanaryPreference.CANARY,
    )

    self.json_response = {
      'task_id': 'deadbeef',
      'request': {
        'properties': {
          'dimensions': [
            {'key': 'cores', 'value': '8'},
            {'key': 'os', 'value': 'Ubuntu'},
            {'key': 'pool', 'value': 'Chrome'},
          ],
        },
        'tags': [
          'build_address:luci.chromium.try/linux_chromium_rel_ng/1',
          'builder:linux_chromium_rel_ng',
          'buildertag:yes',
          'commontag:yes',
          'priority:108',
          'recipe_name:recipe',
          'recipe_repository:https://example.com/repo',
        ]
      }
    }

    swarming.create_task_async(build).get_result()

    # Test swarming request.
    self.assertEqual(
        net.json_request_async.call_args[0][0],
        'https://chromium-swarm.appspot.com/_ah/api/swarming/v1/tasks/new')
    actual_task_def = net.json_request_async.call_args[1]['payload']
    expected_task_def = {
      'name': 'buildbucket:luci.chromium.try:linux_chromium_rel_ng-canary',
      'priority': '108',
      'expiration_secs': '3600',
      'tags': [
        'build_address:luci.chromium.try/linux_chromium_rel_ng/1',
        'buildbucket_bucket:luci.chromium.try',
        'buildbucket_build_id:1',
        'buildbucket_hostname:cr-buildbucket.appspot.com',
        'buildbucket_template_revision:template_rev',
        'builder:linux_chromium_rel_ng',
        'buildertag:yes',
        'commontag:yes',
        ('log_location:logdog://luci-logdog-dev.appspot.com/chromium/'
         'buildbucket/cr-buildbucket.appspot.com/1/+/annotations'),
        'luci_project:chromium',
        'recipe_name:recipe',
        'recipe_repository:https://example.com/repo',
        'recipe_revision:HEAD',
      ],
      'properties': {
        'execution_timeout_secs': '3600',
        'extra_args': [
          'cook',
          '-repository', 'https://example.com/repo',
          '-revision', 'HEAD',
          '-recipe', 'recipe',
          '-properties', json.dumps({
            'buildbucket': {
              'hostname': 'cr-buildbucket.appspot.com',
              'build': {
                'bucket': 'luci.chromium.try',
                'created_by': 'user:john@example.com',
                'created_ts': utils.datetime_to_timestamp(build.create_time),
                'id': '1',
                'tags': [],
              },
            },
            '$recipe_engine/runtime': {
              'is_experimental': False,
              'is_luci': True,
            },
            'build_id': 'buildbucket/cr-buildbucket.appspot.com/1',
            'buildername': 'linux_chromium_rel_ng',
            'buildnumber': 1,
            'predefined-property': 'x',
            'predefined-property-bool': True,
          }, sort_keys=True),
          '-logdog-project', 'chromium',
        ],
        'dimensions': sorted([
          {'key': 'cores', 'value': '8'},
          {'key': 'os', 'value': 'Ubuntu'},
          {'key': 'pool', 'value': 'Chrome'},
        ]),
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
        }
      },
      'pubsub_topic': 'projects/testbed-test/topics/swarming',
      'pubsub_userdata': json.dumps({
        'created_ts': utils.datetime_to_timestamp(utils.utcnow()),
        'swarming_hostname': 'chromium-swarm.appspot.com',
        'build_id': 1L,
      }, sort_keys=True),
      'service_account': 'robot@example.com',
      'numerical_value_for_coverage_in_format_obj': 42,
    }
    self.assertEqual(ununicide(actual_task_def), expected_task_def)

    self.assertEqual(set(build.tags), {
      'build_address:luci.chromium.try/linux_chromium_rel_ng/1',
      'builder:linux_chromium_rel_ng',
      'swarming_dimension:cores:8',
      'swarming_dimension:os:Ubuntu',
      'swarming_dimension:pool:Chrome',
      'swarming_hostname:chromium-swarm.appspot.com',
      'swarming_tag:build_address:luci.chromium.try/linux_chromium_rel_ng/1',
      'swarming_tag:builder:linux_chromium_rel_ng',
      'swarming_tag:buildertag:yes',
      'swarming_tag:commontag:yes',
      'swarming_tag:priority:108',
      'swarming_tag:recipe_name:recipe',
      'swarming_tag:recipe_repository:https://example.com/repo',
      'swarming_task_id:deadbeef',
    })

  def test_create_task_async_no_canary_template_explicit(self):
    build = mkBuild(
        parameters={
          'builder_name': 'linux_chromium_rel_ng',
        },
        tags=['builder:linux_chromium_rel_ng'],
        canary_preference=model.CanaryPreference.CANARY,
    )

    self.task_template_canary = None
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

  @mock.patch('swarming.swarming.should_use_canary_template', autospec=True)
  def test_create_task_async_no_canary_template_implicit(
      self, should_use_canary_template):
    should_use_canary_template.return_value = True
    self.task_template_canary = None
    self.bucket_cfg.swarming.task_template_canary_percentage.value = 54

    self.json_response = {
      'task_id': 'deadbeef',
      'request': {
        'properties': {
          'dimensions': [
            {'key': 'cores', 'value': '8'},
            {'key': 'os', 'value': 'Ubuntu'},
            {'key': 'pool', 'value': 'Chrome'},
          ],
        },
        'tags': [
          'build_address:luci.chromium.try/linux_chromium_rel_ng/1',
          'builder:linux_chromium_rel_ng',
          'buildertag:yes',
          'commontag:yes',
          'priority:108',
          'recipe_name:recipe',
          'recipe_repository:https://example.com/repo',
          'recipe_revision:HEAD',
        ]
      }
    }

    build = mkBuild(
        parameters={'builder_name': 'linux_chromium_rel_ng'},
        tags=['builder:linux_chromium_rel_ng'],
        canary_preference=model.CanaryPreference.AUTO,
    )
    swarming.create_task_async(build).get_result()

    self.assertFalse(build.canary)
    should_use_canary_template.assert_called_with(54)

  def test_create_task_async_override_cfg(self):
    build = mkBuild(
        parameters={
          'builder_name': 'linux_chromium_rel_ng',
          'swarming': {
            'override_builder_cfg': {
              # Override cores dimension.
              'dimensions': ['cores:16'],
              'recipe': {'revision': 'badcoffee'},
            },
          }
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    self.json_response = {
      'task_id': 'deadbeef',
      'request': {
        'properties': {
          'dimensions': [
            {'key': 'cores', 'value': '16'},
            {'key': 'os', 'value': 'Ubuntu'},
            {'key': 'pool', 'value': 'Chrome'},
          ],
        },
        'tags': [
          'build_address:luci.chromium.try/linux_chromium_rel_ng/1',
          'builder:linux_chromium_rel_ng',
          'buildertag:yes',
          'commontag:yes',
          'priority:108',
          'recipe_name:recipe',
          'recipe_repository:https://example.com/repo',
          'recipe_revision:badcoffee',
        ]
      }
    }

    swarming.create_task_async(build).get_result()

    actual_task_def = net.json_request_async.call_args[1]['payload']
    self.assertIn(
        {'key': 'cores', 'value': '16'},
        actual_task_def['properties']['dimensions'])

  def test_create_task_async_override_cfg_malformed(self):
    build = mkBuild(
        parameters={
          'builder_name': 'linux_chromium_rel_ng',
          'swarming': {
            'override_builder_cfg': [],
          }
        },
        tags=['builder:linux_chromium_rel_ng'],
    )
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

    build = mkBuild(
        parameters={
          'builder_name': 'linux_chromium_rel_ng',
          'swarming': {
            'override_builder_cfg': {
              'name': 'x',
            },
          }
        },
        tags=['builder:linux_chromium_rel_ng'],
    )
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

    build = mkBuild(
        parameters={
          'builder_name': 'linux_chromium_rel_ng',
          'swarming': {
            'override_builder_cfg': {
              'mixins': ['x'],
            },
          }
        },
        tags=['builder:linux_chromium_rel_ng'],
    )
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

    build = mkBuild(
        parameters={
          'builder_name': 'linux_chromium_rel_ng',
          'swarming': {
            'override_builder_cfg': {
              'blabla': 'x',
            },
          }
        },
        tags=['builder:linux_chromium_rel_ng'],
    )
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

    # Remove a required dimension.
    build = mkBuild(
        parameters={
          'builder_name': 'linux_chromium_rel_ng',
          'swarming': {
            'override_builder_cfg': {
              'dimensions': ['pool:'],
            },
          }
        },
        tags=['builder:linux_chromium_rel_ng'],
    )
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

    # Override build numbers
    build = mkBuild(
        parameters={
          'builder_name': 'linux_chromium_rel_ng',
          'swarming': {
            'override_builder_cfg': {
              'build_numbers': False,
            },
          }
        },
        tags=['builder:linux_chromium_rel_ng'],
    )
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

  def test_create_task_async_on_leased_build(self):
    build = mkBuild(
        parameters={'builder_name': 'linux_chromium_rel_ng'},
        tags=['builder:linux_chromium_rel_ng'],
        lease_key=12345,
    )
    with self.assertRaises(errors.InvalidInputError):
      swarming.create_task_async(build).get_result()

  def test_create_task_async_without_milo_hostname(self):
    self.settings.milo_hostname = ''
    build = mkBuild(
        parameters={
          'builder_name': 'linux_chromium_rel_ng',
          'swarming': {
            'override_builder_cfg': {
              # Override cores dimension.
              'dimensions': ['cores:16'],
              'recipe': {'revision': 'badcoffee'},
            },
          }
        },
        tags=['builder:linux_chromium_rel_ng'],
    )

    self.json_response = {
      'task_id': 'deadbeef',
      'request': {
        'properties': {
          'dimensions': [
            {'key': 'cores', 'value': '16'},
            {'key': 'os', 'value': 'Ubuntu'},
            {'key': 'pool', 'value': 'Chrome'},
          ],
        },
        'tags': [
          'build_address:luci.chromium.try/linux_chromium_rel_ng/1',
          'builder:linux_chromium_rel_ng',
          'buildertag:yes',
          'commontag:yes',
          'priority:108',
          'recipe_name:recipe',
          'recipe_repository:https://example.com/repo',
          'recipe_revision:badcoffee',
        ]
      }
    }

    swarming.create_task_async(build).get_result()

  def test_cancel_task(self):
    self.json_response = {}
    swarming.cancel_task('chromium-swarm.appspot.com', 'deadbeef')
    net.json_request_async.assert_called_with(
      ('https://chromium-swarm.appspot.com/'
       '_ah/api/swarming/v1/task/deadbeef/cancel'),
      method='POST',
      scopes=net.EMAIL_SCOPE,
      delegation_token=None,
      payload=None,
      deadline=None,
      max_attempts=None,
    )

  @mock.patch('swarming.swarming._load_build_run_result_async', autospec=True)
  def test_sync(self, load_build_run_result_async):
    load_build_run_result_async.return_value = future(None)
    cases = [
      {
        'task_result': None,
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.FAILURE,
        'failure_reason': model.FailureReason.INFRA_FAILURE,
      },
      {
        'task_result': {
          'state': 'PENDING',
        },
        'status': model.BuildStatus.SCHEDULED,
      },
      {
        'task_result': {
          'state': 'RUNNING',
        },
        'status': model.BuildStatus.STARTED,
      },
      {
        'task_result': {
          'state': 'COMPLETED',
        },
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.SUCCESS,
      },
      {
        'task_result': {
          'state': 'COMPLETED',
          'failure': True,
        },
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.FAILURE,
        'failure_reason': model.FailureReason.BUILD_FAILURE,
      },
      {
        'task_result': {
          'state': 'COMPLETED',
          'failure': True,
        },
        'build_run_result': {
          'infra_failure': {
            'type': 'BOOTSTRAPPER_ERROR',
            'text': 'it is not good',
          },
        },
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.FAILURE,
        'failure_reason': model.FailureReason.INFRA_FAILURE,
      },
      {
        'task_result': {
          'state': 'COMPLETED',
          'failure': True,
        },
        'build_run_result_side_effect': swarming.BuildResultFileCorruptedError,
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.FAILURE,
        'failure_reason': model.FailureReason.INFRA_FAILURE,
      },
      {
        'task_result': {
          'state': 'COMPLETED',
          'failure': True,
          'internal_failure': True
        },
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.FAILURE,
        'failure_reason': model.FailureReason.INFRA_FAILURE,
      },
      {
        'task_result': {
          'state': 'BOT_DIED',
        },
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.FAILURE,
        'failure_reason': model.FailureReason.INFRA_FAILURE,
      },
      {
        'task_result': {
          'state': 'TIMED_OUT',
        },
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.FAILURE,
        'failure_reason': model.FailureReason.INFRA_FAILURE,
      },
      {
        'task_result': {
          'state': 'EXPIRED',
        },
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.CANCELED,
        'cancelation_reason': model.CancelationReason.TIMEOUT,
      },
      {
        'task_result': {
          'state': 'CANCELED',
        },
        'status': model.BuildStatus.COMPLETED,
        'result': model.BuildResult.CANCELED,
        'cancelation_reason': model.CancelationReason.CANCELED_EXPLICITLY,
      },
    ]

    for case in cases:
      build = mkBuild(canary=False)
      build.put()
      load_build_run_result_async.side_effect = case.get(
          'build_run_result_side_effect')
      swarming._sync_build_async(
          1, case['task_result'], case.get('build_run_result')).get_result()
      build = build.key.get()
      self.assertEqual(build.status, case['status'])
      self.assertEqual(build.result, case.get('result'))
      self.assertEqual(build.failure_reason, case.get('failure_reason'))
      self.assertEqual(build.cancelation_reason, case.get('cancelation_reason'))
      if build.status == model.BuildStatus.STARTED:
        self.assertEqual(build.start_time, self.now)

  @mock.patch('swarming.isolate.fetch_async')
  def test_load_build_run_result_async(self, fetch_isolate_async):
    self.assertIsNone(swarming._load_build_run_result_async({}).get_result())

    expected = {
      'infra_failure': {
        'text': 'not good',
      },
    }
    fetch_isolate_async.side_effect = [
      # isolated
      future(json.dumps({
        'files': {
          swarming.BUILD_RUN_RESULT_FILENAME: {'h': 'deadbeef'},
        },
      })),
      # build-run-result.json
      future(json.dumps(expected)),
    ]
    actual = swarming._load_build_run_result_async({
      'id': 'taskid',
      'outputs_ref': {
        'isolatedserver': 'https://isolate.example.com',
        'namespace': 'default-gzip',
        'isolated': 'badcoffee',
      }
    }).get_result()
    self.assertEqual(expected, actual)
    fetch_isolate_async.assert_any_call(isolate.Location(
        'isolate.example.com', 'default-gzip', 'badcoffee',
    ))
    fetch_isolate_async.assert_any_call(isolate.Location(
        'isolate.example.com', 'default-gzip', 'deadbeef',
    ))

  @mock.patch('swarming.isolate.fetch_async')
  def test_load_build_run_result_async_no_result(self, fetch_isolate_async):
    # isolated only, without the result
    fetch_isolate_async.return_value = future(json.dumps({
      'files': {
        'soemthing_else.txt': {'h': 'deadbeef'},
      },
    }))
    actual = swarming._load_build_run_result_async({
      'id': 'taskid',
      'outputs_ref': {
        'isolatedserver': 'https://isolate.example.com',
        'namespace': 'default-gzip',
        'isolated': 'badcoffee',
      }
    }).get_result()
    self.assertIsNone(actual)

  def test_load_build_run_result_async_non_https_server(self):
    with self.assertRaises(swarming.BuildResultFileCorruptedError):
      swarming._load_build_run_result_async({
        'id': 'taskid',
        'outputs_ref': {
          'isolatedserver': 'http://isolate.example.com',
          'namespace': 'default-gzip',
          'isolated': 'badcoffee',
        }
      }).get_result()

  @mock.patch('swarming.isolate.fetch_async')
  def test_load_build_run_result_invalid_json(self, fetch_isolate_async):
    fetch_isolate_async.return_value = future('{"incomplete_json')
    with self.assertRaises(swarming.BuildResultFileCorruptedError):
      swarming._load_build_run_result_async({
        'id': 'taskid',
        'outputs_ref': {
          'isolatedserver': 'https://isolate.example.com',
          'namespace': 'default-gzip',
          'isolated': 'badcoffee',
        }
      }).get_result()

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
        }
      }).get_result()

  def test_generate_build_url(self):
    build = mkBuild(
        parameters={swarming.BUILDER_PARAMETER: 'linux_chromium_rel_ng'},
        swarming_hostname='swarming.example.com',
        swarming_task_id='deadbeef',
    )

    self.assertEqual(
        swarming._generate_build_url('milo.example.com', build, 3),
        ('https://milo.example.com/p/chromium/builders/'
         'luci.chromium.try/linux_chromium_rel_ng/3'))

    self.assertEqual(
        swarming._generate_build_url('milo.example.com', build, None),
        ('https://milo.example.com/p/chromium/builds/b1'))

    self.assertEqual(
        swarming._generate_build_url(None, build, 54),
        ('https://swarming.example.com/task?id=deadbeef'))


class SubNotifyTest(BaseTest):
  def setUp(self):
    super(SubNotifyTest, self).setUp()
    self.handler = swarming.SubNotify(response=webapp2.Response())

  def test_unpack_msg(self):
    self.assertEqual(
      self.handler.unpack_msg({
        'data': b64json({
          'task_id': 'deadbeef',
          'userdata': json.dumps({
            'created_ts': 1448841600000000,
            'swarming_hostname': 'chromium-swarm.appspot.com',
            'build_id': 1L,
          })
        })
      }),
      (
        'chromium-swarm.appspot.com',
        datetime.datetime(2015, 11, 30),
        'deadbeef',
        1)
    )

  def test_unpack_msg_with_err(self):
    with self.assert_bad_message():
      self.handler.unpack_msg({})
    with self.assert_bad_message():
      self.handler.unpack_msg({'data': b64json([])})

    bad_data = [
      # Bad task id.
      {
        'userdata': json.dumps({
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
        })
      },

      # Bad creation time
      {
        'task_id': 'deadbeef',
        'userdata': json.dumps({
          'swarming_hostname': 'chromium-swarm.appspot.com',
        })
      },
      {
        'task_id': 'deadbeef',
        'userdata': json.dumps({
          'created_ts': 'foo',
          'swarming_hostname': 'chromium-swarm.appspot.com',
        })
      },
    ]

    for data in bad_data:
      with self.assert_bad_message():
        self.handler.unpack_msg({'data': b64json(data)})

  @mock.patch('swarming.swarming._load_task_result_async', autospec=True)
  def test_post(self, load_task_result_async):
    build = mkBuild(
        parameters={
          'builder_name': 'release'
        },
        tags=['builder:linux_chromium_rel_ng'],
        swarming_hostname='chromium-swarm.appspot.com',
        swarming_task_id='deadbeef',
        canary=False,
    )
    build.put()

    self.handler.request = mock.Mock(json={
      'message': {
        'data': b64json({
          'task_id': 'deadbeef',
          'userdata': json.dumps({
            'build_id': 1L,
            'created_ts': 1448841600000000,
            'swarming_hostname': 'chromium-swarm.appspot.com',
          })
        })
      }
    })
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
        parameters={
          'builder_name': 'release'
        },
        tags=['builder:linux_chromium_rel_ng'],
        swarming_hostname='chromium-swarm.appspot.com',
        swarming_task_id='deadbeef',
    )
    build.put()

    self.handler.request = mock.Mock(json={
      'message': {
        'data': b64json({
          'task_id': 'deadbeef',
          'userdata': json.dumps({
            'build_id': 1L,
            'created_ts': 1448841600000000,
            'swarming_hostname': 'chromium-swarm.appspot.com.au',
          })
        })
      }
    })

    with self.assert_bad_message(expect_redelivery=False):
      self.handler.post()

  def test_post_with_different_task_id(self):
    build = mkBuild(
        parameters={
          'builder_name': 'release'
        },
        tags=['builder:release'],
        swarming_hostname='chromium-swarm.appspot.com',
        swarming_task_id='deadbeef',
    )
    build.put()

    self.handler.request = mock.Mock(json={
      'message': {
        'data': b64json({
          'task_id': 'deadbeefffffffffff',
          'userdata': json.dumps({
            'build_id': 1L,
            'created_ts': 1448841600000000,
            'swarming_hostname': 'chromium-swarm.appspot.com',
          })
        })
      }
    })

    with self.assert_bad_message(expect_redelivery=False):
      self.handler.post()

  def test_post_without_task_id(self):
    self.handler.request = mock.Mock(json={
      'message': {
        'data': b64json({
          'userdata': json.dumps({
            'build_id': 1L,
            'created_ts': 1448841600000000,
            'swarming_hostname': 'chromium-swarm.appspot.com',
          })
        })
      }
    })
    with self.assert_bad_message(expect_redelivery=False):
      self.handler.post()

  def test_post_without_build_id(self):
    self.handler.request = mock.Mock(json={
      'message': {
        'data': b64json({
          'task_id': 'deadbeef',
          'userdata': json.dumps({
            'created_ts': 1448841600000000,
            'swarming_hostname': 'chromium-swarm.appspot.com',
          })
        })
      }
    })
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
      'userdata': json.dumps(userdata)
    }
    self.handler.request = mock.Mock(json={
      'message': {
        'data': b64json(msg_data)
      }
    })

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
    err = exc.HTTPInternalServerError if expect_redelivery else exc.HTTPOk
    with self.assertRaises(err):
      yield
    self.assertTrue(self.handler.bad_message)


class CronUpdateTest(BaseTest):
  def setUp(self):
    super(CronUpdateTest, self).setUp()
    self.build = mkBuild(
        start_time=self.now + datetime.timedelta(seconds=1),
        parameters={
            'builder_name': 'release',
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

    load_task_result_async.return_value = future({
      'state': 'COMPLETED',
    })

    swarming.CronUpdateBuilds().update_build_async(build).get_result()
    build = build.key.get()
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(build.result, model.BuildResult.SUCCESS)
    self.assertIsNone(build.lease_key)
    self.assertIsNotNone(build.complete_time)

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
    self.assertEqual(swarming.apply_if_tags(obj), obj)

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
    self.assertEqual(swarming.apply_if_tags(obj), {
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
    })

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
    self.assertEqual(swarming.apply_if_tags(obj), {
      'tags': [
        'something',
        'other_thing',
      ],
      'some key': ['value', {
        'other_key': 100,
      }],
    })


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
  )
  args.update(kwargs)
  return model.Build(**args)
