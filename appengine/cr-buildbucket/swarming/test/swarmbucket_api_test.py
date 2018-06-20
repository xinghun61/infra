# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json

from components import auth
from components import auth_testing
from testing_utils import testing
import mock

from proto.config import project_config_pb2
from swarming import swarmbucket_api
from test import config_test
from test.test_util import future
import config
import model
import sequence
import v2


class SwarmbucketApiTest(testing.EndpointsTestCase):
  api_service_cls = swarmbucket_api.SwarmbucketApi
  maxDiff = None

  def setUp(self):
    super(SwarmbucketApiTest, self).setUp()

    self.patch(
        'components.utils.utcnow',
        autospec=True,
        return_value=datetime.datetime(2015, 11, 30)
    )

    self.patch(
        'google.appengine.api.app_identity.get_default_version_hostname',
        return_value='cr-buildbucket.appspot.com'
    )

    auth_testing.reset_local_state()
    auth.bootstrap_group('all', [auth.Anonymous])

    chromium_cfg = '''
      name: "luci.chromium.try"
      acls {
        role: SCHEDULER
        group: "all"
      }
      swarming {
        hostname: "swarming.example.com"
        builders {
          name: "linux_chromium_rel_ng"
          category: "Chromium"
          build_numbers: YES
          recipe {
            repository: "https://example.com"
            name: "presubmit"
            properties: "foo:bar"
            properties_j: "baz:1"
          }
          dimensions: "foo:bar"
          dimensions: "baz:baz"
          auto_builder_dimension: YES
        }
        builders {
          name: "win_chromium_rel_ng"
          category: "Chromium"
        }
      }
    '''
    config.Bucket(
        id='luci.chromium.try',
        project_id='chromium',
        revision='deadbeef',
        config_content=chromium_cfg,
        config_content_binary=config_test.text_to_binary(chromium_cfg),
    ).put()

    v8_cfg = '''
      name: "luci.v8.try"
      acls {
        role: READER
        group: "all"
      }
    '''
    config.Bucket(
        id='luci.v8.try',
        project_id='v8',
        revision='deadbeef',
        config_content=v8_cfg,
        config_content_binary=config_test.text_to_binary(v8_cfg),
    ).put()

    self.task_template = {
        'name': 'buildbucket:${bucket}:${builder}',
        'priority': '100',
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
    }

    self.patch(
        'swarming.swarming.get_task_template_async',
        return_value=future(('rev', self.task_template, False))
    )

  def test_get_builders(self):
    secret_cfg = 'name: "secret"'
    config.Bucket(
        id='secret',
        project_id='secret',
        revision='deadbeef',
        config_content=secret_cfg,
        config_content_binary=config_test.text_to_binary(secret_cfg),
    ).put()

    resp = self.call_api('get_builders').json_body
    self.assertEqual(
        resp,
        {
            'buckets': [{
                'name':
                    'luci.chromium.try',
                'swarming_hostname':
                    'swarming.example.com',
                'builders': [
                    {
                        'name':
                            'linux_chromium_rel_ng',
                        'category':
                            'Chromium',
                        'properties_json':
                            json.dumps({'foo': 'bar', 'baz': 1}),
                        'swarming_dimensions': [
                            'baz:baz', 'builder:linux_chromium_rel_ng',
                            'foo:bar'
                        ],
                    },
                    {
                        'name': 'win_chromium_rel_ng',
                        'category': 'Chromium',
                        'properties_json': json.dumps({}),
                    },
                ],
            }],
        },
    )

  def test_get_builders_with_bucket_filtering(self):
    # Add a second bucket with a different name.
    other_bucket = '''
      name: "luci.other.try"
      acls {
        role: SCHEDULER
        group: "all"
      }
      swarming {
        hostname: "swarming.example.com"
        builders {
          name: "a"
        }
      }
    '''
    config.Bucket(
        id='luci.other.try',
        project_id='other',
        revision='deadbeef',
        config_content=other_bucket,
        config_content_binary=config_test.text_to_binary(other_bucket),
    ).put()

    req = {
        'bucket': ['luci.chromium.try'],
    }
    resp = self.call_api('get_builders', req).json_body
    self.assertEqual(
        resp,
        {
            'buckets': [{
                'name':
                    'luci.chromium.try',
                'swarming_hostname':
                    'swarming.example.com',
                'builders': [
                    {
                        'name':
                            'linux_chromium_rel_ng',
                        'category':
                            'Chromium',
                        'properties_json':
                            json.dumps({'foo': 'bar', 'baz': 1}),
                        'swarming_dimensions': [
                            'baz:baz', 'builder:linux_chromium_rel_ng',
                            'foo:bar'
                        ],
                    },
                    {
                        'name': 'win_chromium_rel_ng',
                        'category': 'Chromium',
                        'properties_json': json.dumps({}),
                    },
                ],
            }],
        },
    )

  def test_get_builders_with_bucket_filtering_limit(self):
    req = {
        'bucket': ['luci.chromium.try'] * 200,
    }
    self.call_api('get_builders', req, status=400)

  def test_get_task_def(self):
    req = {
        'build_request': {
            'bucket':
                'luci.chromium.try',
            'parameters_json':
                json.dumps({
                    model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
                }),
        },
    }
    resp = self.call_api('get_task_def', req).json_body
    actual_task_def = json.loads(resp['task_definition'])
    expected_task_def = {
        'name':
            'buildbucket:luci.chromium.try:linux_chromium_rel_ng',
        'tags': [
            'build_address:luci.chromium.try/linux_chromium_rel_ng/0',
            'buildbucket_bucket:luci.chromium.try',
            'buildbucket_build_id:1',
            'buildbucket_hostname:cr-buildbucket.appspot.com',
            'buildbucket_template_canary:0',
            'buildbucket_template_revision:rev',
            'builder:linux_chromium_rel_ng',
            'recipe_name:presubmit',
            'recipe_repository:https://example.com',
        ],
        'priority':
            '100',
        'expiration_secs':
            '3600',
        'pool_task_template':
            'CANARY_NEVER',
        'properties': {
            'env': [{'key': 'BUILDBUCKET_EXPERIMENTAL', 'value': 'FALSE'}],
            'extra_args': [
                'cook',
                '-repository',
                'https://example.com',
                '-revision',
                'HEAD',
                '-recipe',
                'presubmit',
                '-properties',
                json.dumps(
                    {
                        'buildbucket': {
                            'hostname': 'cr-buildbucket.appspot.com',
                            'build': {
                                'project': 'chromium',
                                'bucket': 'luci.chromium.try',
                                'created_by': 'anonymous:anonymous',
                                'created_ts': 1448841600000000,
                                'id': '1',
                                'tags': [],
                            },
                        },
                        '$recipe_engine/runtime': {
                            'is_experimental': False,
                            'is_luci': True,
                        },
                        'foo': 'bar',
                        'baz': 1,
                        'buildername': 'linux_chromium_rel_ng',
                        'buildnumber': 0,
                    },
                    sort_keys=True,
                ),
                '-logdog-project',
                'chromium',
            ],
            'execution_timeout_secs':
                '3600',
            'cipd_input': {
                'packages': [
                    {
                        'path': '.',
                        'package_name': 'infra/test/bar/${os_ver}',
                        'version': 'latest',
                    },
                    {
                        'path': 'third_party',
                        'package_name': 'infra/test/foo/${platform}',
                        'version': 'stable',
                    },
                ],
            },
            'dimensions': [
                {'key': 'baz', 'value': 'baz'},
                {'key': 'builder', 'value': 'linux_chromium_rel_ng'},
                {'key': 'foo', 'value': 'bar'},
            ],
            'caches': [{
                'path':
                    'cache/builder',
                'name': (
                    'builder_980988014eb33bf5578a0f44e123402888e39083523bfd921'
                    '4fea0c8a080db17'
                ),
            }],
        },
    }
    self.assertEqual(actual_task_def, expected_task_def)

  def test_get_task_def_bad_request(self):
    req = {
        'build_request': {
            'bucket':
                ')))',
            'parameters_json':
                json.dumps({
                    model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
                }),
        },
    }
    self.call_api('get_task_def', req, status=400)

    req = {
        'build_request': {'bucket': 'luci.chromium.try'},
    }
    self.call_api('get_task_def', req, status=400)

    req = {
        'build_request': {
            'bucket': 'luci.chromium.try', 'parameters_json': '{}'
        },
    }
    self.call_api('get_task_def', req, status=400)

  def test_get_task_def_builder_not_found(self):
    req = {
        'build_request': {
            'bucket':
                'luci.chromium.try',
            'parameters_json':
                json.dumps({
                    model.BUILDER_PARAMETER: 'not-existing-builder',
                }),
        },
    }
    self.call_api('get_task_def', req, status=404)

  def test_get_task_def_forbidden(self):
    req = {
        'build_id': '8982540789124571952',
        'build_request': {
            'bucket':
                'secret.bucket',
            'parameters_json':
                json.dumps({
                    model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
                }),
        },
    }

    self.call_api('get_task_def', req, status=403)

  @mock.patch('config.get_bucket', autospec=True)
  def test_set_next_build_number(self, get_bucket_cfg):
    get_bucket_cfg.return_value = (
        'project',
        project_config_pb2.Bucket(
            name='a',
            swarming=project_config_pb2.Swarming(
                builders=[
                    project_config_pb2.Builder(name='b'),
                ],
            ),
        ),
    )

    seq = sequence.NumberSequence(id='a/b', next_number=10)
    seq.put()
    req = {
        'bucket': 'a',
        'builder': 'b',
        'next_number': 20,
    }

    self.call_api('set_next_build_number', req, status=403)
    self.assertEqual(seq.key.get().next_number, 10)

    self.patch('user.can_set_next_number', return_value=True)
    self.call_api('set_next_build_number', req)
    self.assertEqual(seq.key.get().next_number, 20)

    req['next_number'] = 10
    self.call_api('set_next_build_number', req, status=400)
    self.assertEqual(seq.key.get().next_number, 20)

    req['builder'] = 'does not exist'
    self.call_api('set_next_build_number', req, status=400)
