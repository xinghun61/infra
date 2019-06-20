# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import contextlib
import copy
import datetime
import json
import logging

from parameterized import parameterized

from components import utils
utils.fix_protobuf_package()

from google import protobuf
from google.appengine.ext import ndb
from google.protobuf import timestamp_pb2

from components import auth
from components import net
from components import utils
from testing_utils import testing
from webob import exc
import mock
import webapp2

from legacy import api_common
from proto import build_pb2
from proto import common_pb2
from proto import launcher_pb2
from proto import project_config_pb2
from proto import service_config_pb2
from test import test_util
from test.test_util import future, future_exception
import bbutil
import errors
import model
import swarming
import user

linux_CACHE_NAME = (
    'builder_ccadafffd20293e0378d1f94d214c63a0f8342d1161454ef0acfa0405178106b'
)

NOW = datetime.datetime(2015, 11, 30)


def tspb(seconds, nanos=0):
  return timestamp_pb2.Timestamp(seconds=seconds, nanos=nanos)


class BaseTest(testing.AppengineTestCase):
  maxDiff = None

  def setUp(self):
    super(BaseTest, self).setUp()
    user.clear_request_cache()

    self.patch('tq.enqueue_async', autospec=True, return_value=future(None))

    self.now = NOW
    self.patch(
        'components.utils.utcnow', autospec=True, side_effect=lambda: self.now
    )

    self.settings = service_config_pb2.SettingsCfg(
        swarming=dict(
            milo_hostname='milo.example.com',
            luci_runner_package=dict(
                package_name='infra/tools/luci_runner',
                version='luci-runner-version',
                version_canary='luci-runner-version-canary',
            ),
            kitchen_package=dict(
                package_name='infra/tools/kitchen',
                version='kitchen-version',
                version_canary='kitchen-version-canary',
            ),
            user_packages=[
                dict(
                    package_name='infra/tools/git',
                    version='git-version',
                    version_canary='git-version-canary',
                ),
            ],
        ),
    )
    self.patch(
        'config.get_settings_async',
        autospec=True,
        return_value=future(self.settings)
    )


class TaskDefTest(BaseTest):

  def setUp(self):
    super(TaskDefTest, self).setUp()

    self.task_template = {
        'name':
            'bb-${build_id}-${project}-${builder}',
        'priority':
            100,
        'tags': [
            (
                'log_location:logdog://luci-logdog-dev.appspot.com/${project}/'
                'buildbucket/${hostname}/${build_id}/+/annotations'
            ),
            'luci_project:${project}',
        ],
        'task_slices': [{
            'properties': {
                'extra_args': [
                    'cook',
                    '-recipe',
                    '${recipe}',
                    '-properties',
                    '${properties_json}',
                    '-logdog-project',
                    '${project}',
                ],
            },
            'wait_for_capacity': False,
        },],
    }
    self.task_template_canary = self.task_template.copy()
    self.task_template_canary['name'] += '-canary'

    def get_self_config(path, *_args, **_kwargs):
      if path not in ('swarming_task_template.json',
                      'swarming_task_template_canary.json'):  # pragma: no cover
        self.fail()

      if path == 'swarming_task_template.json':
        template = self.task_template
      else:
        template = self.task_template_canary
      return (
          'template_rev',
          json.dumps(template) if template is not None else None,
      )

    self.patch(
        'components.config.get_self_config',
        side_effect=get_self_config,
        autospec=True,
    )

    self.patch(
        'google.appengine.api.app_identity.get_default_version_hostname',
        return_value='cr-buildbucket.appspot.com'
    )

  def _test_build(self, **build_proto_fields):
    return test_util.build(for_creation=True, **build_proto_fields)

  def prepare_task_def(self, build):
    return swarming.prepare_task_def(build, self.settings.swarming)

  def test_shared_cache(self):
    build = self._test_build(
        infra=dict(
            swarming=dict(
                caches=[
                    dict(path='builder', name='shared_builder_cache'),
                ],
            ),
        ),
    )

    slices = self.prepare_task_def(build)['task_slices']
    self.assertEqual(
        slices[0]['properties']['caches'], [
            {'path': 'cache/builder', 'name': 'shared_builder_cache'},
        ]
    )

  def test_dimensions_and_cache_fallback(self):
    # Creates 4 task_slices by modifying the buildercfg in 2 ways:
    # - Add two named caches, one expiring at 60 seconds, one at 360 seconds.
    # - Add an optional builder dimension, expiring at 120 seconds.
    #
    # This ensures the combination of these features works correctly, and that
    # multiple 'caches' dimensions can be injected.
    build = self._test_build(
        scheduling_timeout=dict(seconds=3600),
        infra=dict(
            swarming=dict(
                caches=[
                    dict(
                        path='builder',
                        name='shared_builder_cache',
                        wait_for_warm_cache=dict(seconds=60),
                    ),
                    dict(
                        path='second',
                        name='second_cache',
                        wait_for_warm_cache=dict(seconds=360),
                    ),
                ],
                task_dimensions=[
                    dict(key='a', value='1', expiration=dict(seconds=120)),
                    dict(key='pool', value='Chrome'),
                ]
            )
        )
    )

    slices = self.prepare_task_def(build)['task_slices']

    self.assertEqual(4, len(slices))
    for t in slices:
      # They all use the same cache definitions.
      self.assertEqual(
          t['properties']['caches'], [
              {'path': u'cache/builder', 'name': u'shared_builder_cache'},
              {'path': u'cache/second', 'name': u'second_cache'},
          ]
      )

    # But the dimensions are different. 'a' and 'caches' are injected.
    self.assertEqual(
        slices[0]['properties']['dimensions'], [
            {u'key': u'a', u'value': u'1'},
            {u'key': u'caches', u'value': u'second_cache'},
            {u'key': u'caches', u'value': u'shared_builder_cache'},
            {u'key': u'pool', u'value': u'Chrome'},
        ]
    )
    self.assertEqual(slices[0]['expiration_secs'], '60')

    # One 'caches' expired. 'a' and one 'caches' are still injected.
    self.assertEqual(
        slices[1]['properties']['dimensions'], [
            {u'key': u'a', u'value': u'1'},
            {u'key': u'caches', u'value': u'second_cache'},
            {u'key': u'pool', u'value': u'Chrome'},
        ]
    )
    # 120-60
    self.assertEqual(slices[1]['expiration_secs'], '60')

    # 'a' expired, one 'caches' remains.
    self.assertEqual(
        slices[2]['properties']['dimensions'], [
            {u'key': u'caches', u'value': u'second_cache'},
            {u'key': u'pool', u'value': u'Chrome'},
        ]
    )
    # 360-120
    self.assertEqual(slices[2]['expiration_secs'], '240')

    # The cold fallback; the last 'caches' expired.
    self.assertEqual(
        slices[3]['properties']['dimensions'], [
            {u'key': u'pool', u'value': u'Chrome'},
        ]
    )
    # 3600-360
    self.assertEqual(slices[3]['expiration_secs'], '3240')

  def test_execution_timeout(self):
    build = self._test_build(execution_timeout=dict(seconds=120))
    slices = self.prepare_task_def(build)['task_slices']

    self.assertEqual(slices[0]['properties']['execution_timeout_secs'], '120')

  def test_scheduling_timeout(self):
    build = self._test_build(scheduling_timeout=dict(seconds=120))
    slices = self.prepare_task_def(build)['task_slices']

    self.assertEqual(1, len(slices))
    self.assertEqual(slices[0]['expiration_secs'], '120')

  def test_compute_cipd_input_canary(self):
    build = self._test_build(canary=True)
    cipd_input = swarming._compute_cipd_input(build, self.settings.swarming)
    packages = {p['package_name']: p for p in cipd_input['packages']}
    self.assertEqual(
        packages['infra/tools/luci_runner']['version'],
        'luci-runner-version-canary',
    )
    self.assertEqual(
        packages['infra/tools/git']['version'],
        'git-version-canary',
    )

  def test_properties(self):
    self.patch(
        'components.auth.get_current_identity',
        autospec=True,
        return_value=auth.Identity('user', 'john@example.com')
    )

    build = self._test_build(
        id=1,
        number=1,
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux'
        ),
        exe=dict(
            cipd_package='infra/recipe_bundle',
            cipd_version='refs/heads/master',
        ),
        input=dict(
            properties=bbutil.dict_to_struct({
                'a': 'b',
                'recipe': 'recipe',
            }),
            gerrit_changes=[
                dict(
                    host='chromium-review.googlesource.com',
                    project='chromium/src',
                    change=1234,
                    patchset=5,
                ),
            ],
        ),
        infra=dict(
            swarming=dict(
                task_service_account='robot@example.com',
                priority=108,
                task_dimensions=[
                    dict(key='cores', value='8'),
                    dict(key='os', value='Ubuntu'),
                    dict(key='pool', value='Chrome'),
                ],
            ),
        ),
    )

    _, extra_task_template_params = swarming._setup_recipes(build)
    actual = json.loads(extra_task_template_params['properties_json'])

    expected = {
        'a': 'b',
        'buildbucket': {
            'hostname': 'cr-buildbucket.appspot.com',
            'build': {
                'project':
                    'chromium',
                'bucket':
                    'luci.chromium.try',
                'created_by':
                    'anonymous:anonymous',
                'created_ts':
                    1448841600000000,
                'id':
                    '1',
                'tags': [
                    'build_address:luci.chromium.try/linux/1',
                    'builder:linux',
                    'buildset:1',
                ],
            },
        },
        'buildername': 'linux',
        'buildnumber': 1,
        'recipe': 'recipe',
        'repository': 'https://chromium.googlesource.com/chromium/src',
        '$recipe_engine/buildbucket': {
            'hostname': 'cr-buildbucket.appspot.com',
            'build': {
                'id': '1',
                'builder': {
                    'project': 'chromium',
                    'bucket': 'try',
                    'builder': 'linux',
                },
                'number': 1,
                'tags': [{'value': '1', 'key': 'buildset'}],
                'exe': {
                    'cipdPackage': 'infra/recipe_bundle',
                    'cipdVersion': 'refs/heads/master',
                },
                'input': {
                    'gerritChanges': [{
                        'host': 'chromium-review.googlesource.com',
                        'project': 'chromium/src',
                        'change': '1234',
                        'patchset': '5',
                    }],
                },
                'infra': {
                    'buildbucket': {},
                    'swarming': {
                        'hostname':
                            'swarming.example.com',
                        'taskId':
                            'deadbeef',
                        'taskServiceAccount':
                            'robot@example.com',
                        'priority':
                            108,
                        'taskDimensions': [
                            {'key': 'cores', 'value': '8'},
                            {'key': 'os', 'value': 'Ubuntu'},
                            {'key': 'pool', 'value': 'Chrome'},
                        ],
                    },
                    'logdog': {
                        'hostname': 'logdog.example.com',
                        'project': 'chromium',
                        'prefix': 'bb',
                    },
                },
                'createdBy': 'anonymous:anonymous',
                'createTime': '2015-11-30T00:00:00Z',
            },
        },
        '$recipe_engine/runtime': {
            'is_experimental': False,
            'is_luci': True,
        },
    }
    self.assertEqual(test_util.ununicode(actual), expected)

  def test_overall(self):
    self.patch(
        'components.auth.get_current_identity',
        autospec=True,
        return_value=auth.Identity('user', 'john@example.com')
    )

    build = self._test_build(
        id=1,
        number=1,
        scheduling_timeout=dict(seconds=3600),
        execution_timeout=dict(seconds=3600),
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux'
        ),
        exe=dict(
            cipd_package='infra/recipe_bundle',
            cipd_version='refs/heads/master',
        ),
        input=dict(
            properties=bbutil.dict_to_struct({
                'a': 'b',
                'recipe': 'recipe',
            }),
            gerrit_changes=[
                dict(
                    host='chromium-review.googlesource.com',
                    project='chromium/src',
                    change=1234,
                    patchset=5,
                ),
            ],
        ),
        infra=dict(
            swarming=dict(
                task_service_account='robot@example.com',
                priority=108,
                task_dimensions=[
                    dict(key='cores', value='8'),
                    dict(key='os', value='Ubuntu'),
                    dict(key='pool', value='Chrome'),
                ],
                caches=[
                    dict(path='a', name='1'),
                ],
            ),
        ),
    )

    actual = self.prepare_task_def(build)

    expected_swarming_props_def = {
        'env': [{
            'key': 'BUILDBUCKET_EXPERIMENTAL',
            'value': 'FALSE',
        }],
        'execution_timeout_secs':
            '3600',
        'extra_args': [
            'cook',
            '-recipe',
            'recipe',
            '-properties',
            # Properties are tested by test_properties() above.
            swarming._setup_recipes(build)[1]['properties_json'],
            '-logdog-project',
            'chromium',
        ],
        'dimensions': [
            {'key': 'cores', 'value': '8'},
            {'key': 'os', 'value': 'Ubuntu'},
            {'key': 'pool', 'value': 'Chrome'},
        ],
        'caches': [{'path': 'cache/a', 'name': '1'}],
        'cipd_input': {
            'packages': [
                {
                    'package_name': 'infra/tools/luci_runner',
                    'path': '.',
                    'version': 'luci-runner-version',
                },
                {
                    'package_name': 'infra/tools/kitchen',
                    'path': '.',
                    'version': 'kitchen-version',
                },
                {
                    'package_name': 'infra/recipe_bundle',
                    'path': 'kitchen-checkout',
                    'version': 'refs/heads/master',
                },
                {
                    'package_name': 'infra/tools/git',
                    'path': swarming.USER_PACKAGE_DIR,
                    'version': 'git-version',
                },
            ],
        },
    }
    expected = {
        'name':
            'bb-1-chromium-linux',
        'priority':
            '108',
        'tags': [
            'build_address:luci.chromium.try/linux/1',
            'buildbucket_bucket:chromium/try',
            'buildbucket_build_id:1',
            'buildbucket_hostname:cr-buildbucket.appspot.com',
            'buildbucket_template_canary:0',
            'buildbucket_template_revision:template_rev',
            'builder:linux',
            'buildset:1',
            (
                'log_location:logdog://luci-logdog-dev.appspot.com/chromium/'
                'buildbucket/cr-buildbucket.appspot.com/1/+/annotations'
            ),
            'luci_project:chromium',
            'recipe_name:recipe',
            'recipe_package:infra/recipe_bundle',
        ],
        'pool_task_template':
            'CANARY_NEVER',
        'task_slices': [{
            'expiration_secs': '3600',
            'properties': expected_swarming_props_def,
            'wait_for_capacity': False,
        }],
        'pubsub_topic':
            'projects/testbed-test/topics/swarming',
        'pubsub_userdata':
            json.dumps({
                'created_ts': 1448841600000000,
                'swarming_hostname': 'swarming.example.com',
                'build_id': 1L,
            },
                       sort_keys=True),
        'service_account':
            'robot@example.com',
    }
    self.assertEqual(test_util.ununicode(actual), expected)

    self.assertEqual(build.url, 'https://milo.example.com/b/1')

    self.assertEqual(
        build.proto.infra.swarming.task_service_account, 'robot@example.com'
    )

    self.assertNotIn('buildbucket', build.proto.input.properties)
    self.assertNotIn('$recipe_engine/buildbucket', build.proto.input.properties)

  def test_experimental(self):
    build = self._test_build(input=dict(experimental=True))
    actual = self.prepare_task_def(build)

    env = actual['task_slices'][0]['properties']['env']
    self.assertIn({
        'key': 'BUILDBUCKET_EXPERIMENTAL',
        'value': 'TRUE',
    }, env)

  def test_canary_template(self):
    build = self._test_build(id=1, canary=common_pb2.YES)

    actual = self.prepare_task_def(build)
    self.assertTrue(actual['name'].endswith('-canary'))

  def test_generate_build_url(self):
    build = self._test_build(id=1)
    self.assertEqual(
        swarming._generate_build_url('milo.example.com', build),
        'https://milo.example.com/b/1',
    )

    self.assertEqual(
        swarming._generate_build_url(None, build),
        ('https://swarming.example.com/task?id=deadbeef')
    )

  @parameterized.expand([
      ([], [], True),
      ([], ['chromium/.+'], False),
      ([], ['v8/.+'], True),
      (['chromium/.+'], [], True),
      (['v8/.+'], [], False),
  ])
  def test_builder_matches(self, regex, regex_exclude, expected):
    predicate = service_config_pb2.BuilderPredicate(
        regex=regex, regex_exclude=regex_exclude
    )
    builder_id = build_pb2.BuilderID(
        project='chromium',
        bucket='try',
        builder='linux-rel',
    )
    actual = swarming._builder_matches(builder_id, predicate)
    self.assertEqual(expected, actual)


class CreateTaskTest(BaseTest):

  def setUp(self):
    super(CreateTaskTest, self).setUp()
    self.patch('components.net.json_request_async', autospec=True)
    self.patch('components.auth.delegate_async', return_value=future('blah'))

    self.build_token = 'beeff00d'
    self.patch(
        'tokens.generate_build_token', autospec=True, return_value='deadbeef'
    )

    self.task_def = {'is_task_def': True, 'task_slices': [{
        'properties': {},
    }]}
    self.patch(
        'swarming.prepare_task_def', autospec=True, return_value=self.task_def
    )

    self.build = test_util.build(id=1, created_by='user:john@example.com')
    self.build.swarming_task_key = None
    with self.build.mutate_infra() as infra:
      infra.swarming.task_id = ''
    self.build.put()

  def test_success(self):
    expected_task_def = self.task_def.copy()
    expected_secrets = launcher_pb2.BuildSecrets(build_token=self.build_token)
    expected_task_def[u'task_slices'][0][u'properties'][u'secret_bytes'] = (
        base64.b64encode(expected_secrets.SerializeToString())
    )

    net.json_request_async.return_value = future({'task_id': 'x'})
    swarming._create_swarming_task(1)

    actual_task_def = net.json_request_async.call_args[1]['payload']
    self.assertEqual(actual_task_def, expected_task_def)

    self.assertEqual(
        net.json_request_async.call_args[0][0],
        'https://swarming.example.com/_ah/api/swarming/v1/tasks/new'
    )

    # Test delegation token params.
    self.assertEqual(
        auth.delegate_async.mock_calls, [
            mock.call(
                services=[u'https://swarming.example.com'],
                audience=[auth.Identity('user', 'test@localhost')],
                impersonate=auth.Identity('user', 'john@example.com'),
                tags=['buildbucket:bucket:chromium/try'],
            )
        ]
    )

  def test_already_exists(self):
    with self.build.mutate_infra() as infra:
      infra.swarming.task_id = 'exists'
    self.build.put()

    swarming._create_swarming_task(1)
    self.assertFalse(net.json_request_async.called)

  @mock.patch('swarming.cancel_task', autospec=True)
  def test_already_exists_after_creation(self, cancel_task):

    @ndb.tasklet
    def json_request_async(*_args, **_kwargs):
      with self.build.mutate_infra() as infra:
        infra.swarming.task_id = 'deadbeef'
      yield self.build.put_async()
      raise ndb.Return({'task_id': 'new task'})

    net.json_request_async.side_effect = json_request_async

    swarming._create_swarming_task(1)
    cancel_task.assert_called_with('swarming.example.com', 'new task')

  def test_http_400(self):
    net.json_request_async.return_value = future_exception(
        net.Error('HTTP 401', 400, 'invalid request')
    )

    swarming._create_swarming_task(1)

    build = self.build.key.get()
    self.assertEqual(build.status, common_pb2.INFRA_FAILURE)
    self.assertEqual(
        build.proto.summary_markdown,
        r'Swarming task creation API responded with HTTP 400: `invalid request`'
    )

  def test_http_500(self):
    net.json_request_async.return_value = future_exception(
        net.Error('internal', 500, 'Internal server error')
    )

    with self.assertRaises(net.Error):
      swarming._create_swarming_task(1)


class CancelTest(BaseTest):

  def setUp(self):
    super(CancelTest, self).setUp()

    self.json_response = None

    def json_request_async(*_, **__):
      if self.json_response is not None:
        return future(self.json_response)
      self.fail('unexpected outbound request')  # pragma: no cover

    self.patch(
        'components.net.json_request_async',
        autospec=True,
        side_effect=json_request_async
    )

  def test_cancel_task(self):
    self.json_response = {'ok': True}
    swarming.cancel_task('swarming.example.com', 'deadbeef')
    net.json_request_async.assert_called_with(
        (
            'https://swarming.example.com/'
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


class SyncBuildTest(BaseTest):

  def test_validate(self):
    build = test_util.build()
    swarming.validate_build(build)

  def test_validate_lease_key(self):
    build = test_util.build()
    build.lease_key = 123
    with self.assertRaises(errors.InvalidInputError):
      swarming.validate_build(build)

  @parameterized.expand([
      (
          dict(
              infra=dict(
                  swarming=dict(
                      task_dimensions=[
                          dict(
                              key='a',
                              value='b',
                              expiration=dict(seconds=60 * i)
                          ) for i in xrange(7)
                      ],
                  ),
              ),
          ),
      ),
  ])
  def test_validate_fails(self, build_params):
    build = test_util.build(for_creation=True, **build_params)
    with self.assertRaises(errors.InvalidInputError):
      swarming.validate_build(build)

  @parameterized.expand([
      ({
          'task_result': None,
          'status': common_pb2.INFRA_FAILURE,
          'end_time': test_util.dt2ts(NOW),
      },),
      ({
          'task_result': {'state': 'PENDING'},
          'status': common_pb2.SCHEDULED,
      },),
      ({
          'task_result': {
              'state': 'RUNNING',
              'started_ts': '2018-01-29T21:15:02.649750',
          },
          'status': common_pb2.STARTED,
          'start_time': tspb(seconds=1517260502, nanos=649750000),
      },),
      ({
          'task_result': {
              'state': 'COMPLETED',
              'started_ts': '2018-01-29T21:15:02.649750',
              'completed_ts': '2018-01-30T00:15:18.162860',
          },
          'status': common_pb2.SUCCESS,
          'start_time': tspb(seconds=1517260502, nanos=649750000),
          'end_time': tspb(seconds=1517271318, nanos=162860000),
      },),
      ({
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
          'status':
              common_pb2.SUCCESS,
          'bot_dimensions': [
              common_pb2.StringPair(key='id', value='bot1'),
              common_pb2.StringPair(key='os', value='Trusty'),
              common_pb2.StringPair(key='os', value='Ubuntu'),
              common_pb2.StringPair(key='pool', value='luci.chromium.try'),
          ],
          'start_time':
              tspb(seconds=1517260502, nanos=649750000),
          'end_time':
              tspb(seconds=1517271318, nanos=162860000),
      },),
      ({
          'task_result': {
              'state': 'COMPLETED',
              'failure': True,
              'started_ts': '2018-01-29T21:15:02.649750',
              'completed_ts': '2018-01-30T00:15:18.162860',
          },
          'status': common_pb2.FAILURE,
          'start_time': tspb(seconds=1517260502, nanos=649750000),
          'end_time': tspb(seconds=1517271318, nanos=162860000),
      },),
      ({
          'task_result': {
              'state': 'COMPLETED',
              'failure': True,
              'internal_failure': True,
              'started_ts': '2018-01-29T21:15:02.649750',
              'completed_ts': '2018-01-30T00:15:18.162860',
          },
          'status': common_pb2.INFRA_FAILURE,
          'start_time': tspb(seconds=1517260502, nanos=649750000),
          'end_time': tspb(seconds=1517271318, nanos=162860000),
      },),
      ({
          'task_result': {
              'state': 'BOT_DIED',
              'started_ts': '2018-01-29T21:15:02.649750',
              'abandoned_ts': '2018-01-30T00:15:18.162860',
          },
          'status': common_pb2.INFRA_FAILURE,
          'start_time': tspb(seconds=1517260502, nanos=649750000),
          'end_time': tspb(seconds=1517271318, nanos=162860000),
      },),
      ({
          'task_result': {
              'state': 'TIMED_OUT',
              'started_ts': '2018-01-29T21:15:02.649750',
              'completed_ts': '2018-01-30T00:15:18.162860',
          },
          'status': common_pb2.INFRA_FAILURE,
          'is_timeout': True,
          'start_time': tspb(seconds=1517260502, nanos=649750000),
          'end_time': tspb(seconds=1517271318, nanos=162860000),
      },),
      ({
          'task_result': {
              'state': 'EXPIRED',
              'abandoned_ts': '2018-01-30T00:15:18.162860',
          },
          'status': common_pb2.INFRA_FAILURE,
          'is_resource_exhaustion': True,
          'is_timeout': True,
          'end_time': tspb(seconds=1517271318, nanos=162860000),
      },),
      ({
          'task_result': {
              'state': 'KILLED',
              'abandoned_ts': '2018-01-30T00:15:18.162860',
          },
          'status': common_pb2.CANCELED,
          'end_time': tspb(seconds=1517271318, nanos=162860000),
      },),
      ({
          'task_result': {
              'state': 'CANCELED',
              'abandoned_ts': '2018-01-30T00:15:18.162860',
          },
          'status': common_pb2.CANCELED,
          'end_time': tspb(seconds=1517271318, nanos=162860000),
      },),
      ({
          'task_result': {
              'state': 'NO_RESOURCE',
              'abandoned_ts': '2018-01-30T00:15:18.162860',
          },
          'status': common_pb2.INFRA_FAILURE,
          'is_resource_exhaustion': True,
          'end_time': tspb(seconds=1517271318, nanos=162860000),
      },),
      # NO_RESOURCE with abandoned_ts before creation time.
      (
          {
              'task_result': {
                  'state': 'NO_RESOURCE',
                  'abandoned_ts': '2015-11-29T00:15:18.162860',
              },
              'status': common_pb2.INFRA_FAILURE,
              'is_resource_exhaustion': True,
              'end_time': test_util.dt2ts(NOW),
          },
      ),
  ])
  def test_sync(self, case):
    logging.info('test case: %s', case)
    build = test_util.build(id=1)
    build.put()

    swarming._sync_build_async(1, case['task_result']).get_result()

    build = build.key.get()
    bp = build.proto
    self.assertEqual(bp.status, case['status'])
    self.assertEqual(
        bp.status_details.HasField('timeout'),
        case.get('is_timeout', False),
    )
    self.assertEqual(
        bp.status_details.HasField('resource_exhaustion'),
        case.get('is_resource_exhaustion', False)
    )

    self.assertEqual(bp.start_time, case.get('start_time', tspb(0)))
    self.assertEqual(bp.end_time, case.get('end_time', tspb(0)))
    self.assertEqual(
        list(build.parse_infra().swarming.bot_dimensions),
        case.get('bot_dimensions', [])
    )


class SubNotifyTest(BaseTest):

  def setUp(self):
    super(SubNotifyTest, self).setUp()
    self.handler = swarming.SubNotify(response=webapp2.Response())

  def test_unpack_msg(self):
    self.assertEqual(
        self.handler.unpack_msg({
            'messageId':
                '1', 'data':
                    b64json({
                        'task_id':
                            'deadbeef',
                        'userdata':
                            json.dumps({
                                'created_ts': 1448841600000000,
                                'swarming_hostname': 'swarming.example.com',
                                'build_id': 1L,
                            })
                    })
        }), (
            'swarming.example.com', datetime.datetime(2015, 11, 30), 'deadbeef',
            1
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
                    'swarming_hostname': 'swarming.example.com',
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
                    'swarming_hostname': 'swarming.example.com',
                }),
        },
        {
            'task_id':
                'deadbeef',
            'userdata':
                json.dumps({
                    'created_ts': 'foo',
                    'swarming_hostname': 'swarming.example.com',
                }),
        },
    ]

    for data in bad_data:
      with self.assert_bad_message():
        self.handler.unpack_msg({'data': b64json(data)})

  def mock_request(self, user_data, task_id='deadbeef'):
    msg_data = b64json({
        'task_id': task_id,
        'userdata': json.dumps(user_data),
    })
    self.handler.request = mock.Mock(
        json={
            'message': {
                'messageId': '1',
                'data': msg_data,
            },
        }
    )

  @mock.patch('swarming._load_task_result_async', autospec=True)
  def test_post(self, load_task_result_async):
    build = test_util.build(id=1)
    build.put()

    self.mock_request({
        'build_id': 1L,
        'created_ts': 1448841600000000,
        'swarming_hostname': 'swarming.example.com',
    })

    load_task_result_async.return_value = future({
        'task_id': 'deadbeef',
        'state': 'COMPLETED',
    })

    self.handler.post()

    build = build.key.get()
    self.assertEqual(build.proto.status, common_pb2.SUCCESS)

  def test_post_with_different_swarming_hostname(self):
    build = test_util.build(id=1)
    build.put()

    self.mock_request({
        'build_id': 1L,
        'created_ts': 1448841600000000,
        'swarming_hostname': 'different-chromium.example.com',
    })

    with self.assert_bad_message(expect_redelivery=False):
      self.handler.post()

  def test_post_with_different_task_id(self):
    build = test_util.build(id=1)
    build.put()

    self.mock_request(
        {
            'build_id': 1L,
            'created_ts': 1448841600000000,
            'swarming_hostname': 'swarming.example.com',
        },
        task_id='deadbeefffffffffff',
    )

    with self.assert_bad_message(expect_redelivery=False):
      self.handler.post()

  def test_post_too_soon(self):
    build = test_util.build(id=1)
    with build.mutate_infra() as infra:
      infra.swarming.task_id = ''
    build.put()

    self.mock_request({
        'build_id': 1L,
        'created_ts': 1448841600000000,
        'swarming_hostname': 'swarming.example.com',
    })

    with self.assert_bad_message(expect_redelivery=True):
      self.handler.post()

  def test_post_without_task_id(self):
    self.mock_request(
        {
            'build_id': 1L,
            'created_ts': 1448841600000000,
            'swarming_hostname': 'swarming.example.com',
        },
        task_id=None,
    )

    with self.assert_bad_message(expect_redelivery=False):
      self.handler.post()

  def test_post_without_build_id(self):
    self.mock_request({
        'created_ts': 1448841600000000,
        'swarming_hostname': 'swarming.example.com',
    })
    with self.assert_bad_message(expect_redelivery=False):
      self.handler.post()

  def test_post_without_build(self):
    self.mock_request({
        'created_ts': 1438841600000000,
        'swarming_hostname': 'swarming.example.com',
        'build_id': 1L,
    })

    with self.assert_bad_message(expect_redelivery=False):
      self.handler.post()

  @contextlib.contextmanager
  def assert_bad_message(self, expect_redelivery=False):
    self.handler.bad_message = False
    err = exc.HTTPClientError if expect_redelivery else exc.HTTPOk
    with self.assertRaises(err):
      yield
    self.assertTrue(self.handler.bad_message)

  @mock.patch('swarming.SubNotify._process_msg', autospec=True)
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
    self.now += datetime.timedelta(minutes=5)

  @mock.patch('swarming._load_task_result_async', autospec=True)
  def test_sync_build_async(self, load_task_result_async):
    load_task_result_async.return_value = future({
        'state': 'RUNNING',
    })

    build = test_util.build()
    build.put()

    swarming.CronUpdateBuilds().update_build_async(build).get_result()
    build = build.key.get()
    self.assertEqual(build.proto.status, common_pb2.STARTED)
    self.assertFalse(build.proto.HasField('end_time'))

    load_task_result_async.return_value = future({
        'state': 'COMPLETED',
    })

    swarming.CronUpdateBuilds().update_build_async(build).get_result()
    build = build.key.get()
    self.assertEqual(build.proto.status, common_pb2.SUCCESS)

  @mock.patch('swarming._load_task_result_async', autospec=True)
  def test_sync_build_async_no_task(self, load_task_result_async):
    load_task_result_async.return_value = future(None)

    build = test_util.build()
    build.put()
    swarming.CronUpdateBuilds().update_build_async(build).get_result()
    build = build.key.get()
    self.assertEqual(build.proto.status, common_pb2.INFRA_FAILURE)
    self.assertTrue(build.proto.summary_markdown)

  def test_sync_build_async_non_swarming(self):
    build = test_util.build(status=common_pb2.SCHEDULED)
    with build.mutate_infra() as infra:
      infra.ClearField('swarming')
    build.put()

    swarming.CronUpdateBuilds().update_build_async(build).get_result()

    build = build.key.get()
    self.assertEqual(build.proto.status, common_pb2.SCHEDULED)

  def test_parse_ts_without_usecs(self):
    actual = swarming._parse_ts('2018-02-23T04:22:45')
    expected = datetime.datetime(2018, 2, 23, 4, 22, 45)
    self.assertEqual(actual, expected)


def b64json(data):
  return base64.b64encode(json.dumps(data))
