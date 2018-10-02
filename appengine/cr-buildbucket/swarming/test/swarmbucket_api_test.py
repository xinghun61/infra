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
import user
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
    user.clear_request_cache()

    chromium_cfg = config_test.parse_bucket_cfg(
        '''
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
    )
    config.put_bucket('chromium', 'deadbeef', chromium_cfg)

    v8_cfg = config_test.parse_bucket_cfg(
        '''
      name: "luci.v8.try"
      acls {
        role: READER
        group: "all"
      }
    '''
    )
    config.put_bucket('v8', 'deadbeef', v8_cfg)

    props_def = {
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
    }
    self.task_template = {
        'name':
            'buildbucket:${bucket}:${builder}',
        'priority':
            '100',
        'task_slices': [{
            'expiration_secs': '3600',
            'properties': props_def,
            'wait_for_capacity': False,
        }],
    }

    self.patch(
        'swarming.swarming._get_task_template_async',
        return_value=future(('rev', self.task_template, False))
    )

  def test_get_builders(self):
    secret_cfg = 'name: "secret"'
    config.put_bucket(
        'secret', 'deadbeef', config_test.parse_bucket_cfg(secret_cfg)
    )

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
    config.put_bucket(
        'other', 'deadbeef', config_test.parse_bucket_cfg(other_bucket)
    )

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
    props_def = {
        u'env': [{u'key': u'BUILDBUCKET_EXPERIMENTAL', u'value': u'FALSE'}],
        u'extra_args': [
            u'cook',
            u'-repository',
            u'https://example.com',
            u'-revision',
            u'HEAD',
            u'-recipe',
            u'presubmit',
            u'-properties',
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
            u'-logdog-project',
            u'chromium',
        ],
        u'execution_timeout_secs':
            u'3600',
        u'cipd_input': {
            u'packages': [
                {
                    u'path': u'.',
                    u'package_name': u'infra/test/bar/${os_ver}',
                    u'version': u'latest',
                },
                {
                    u'path': u'third_party',
                    u'package_name': u'infra/test/foo/${platform}',
                    u'version': u'stable',
                },
            ],
        },
        u'dimensions': [
            {u'key': u'baz', u'value': u'baz'},
            {u'key': u'builder', u'value': u'linux_chromium_rel_ng'},
            {u'key': u'foo', u'value': u'bar'},
        ],
        u'caches': [{
            u'path':
                u'cache/builder',
            u'name': (
                u'builder_980988014eb33bf5578a0f44e123402888e39083523bfd921'
                u'4fea0c8a080db17'
            ),
        }],
    }
    expected_task_def = {
        u'name':
            u'buildbucket:luci.chromium.try:linux_chromium_rel_ng',
        u'tags': [
            u'build_address:luci.chromium.try/linux_chromium_rel_ng/0',
            u'buildbucket_bucket:luci.chromium.try',
            u'buildbucket_build_id:1',
            u'buildbucket_hostname:cr-buildbucket.appspot.com',
            u'buildbucket_template_canary:0',
            u'buildbucket_template_revision:rev',
            u'builder:linux_chromium_rel_ng',
            u'recipe_name:presubmit',
            u'recipe_repository:https://example.com',
        ],
        u'priority':
            u'100',
        u'pool_task_template':
            u'CANARY_NEVER',
        u'task_slices': [{
            u'expiration_secs': u'3600',
            u'properties': props_def,
            u'wait_for_capacity': False,
        }],
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

    self.patch('user.can_set_next_number_async', return_value=future(True))
    self.call_api('set_next_build_number', req)
    self.assertEqual(seq.key.get().next_number, 20)

    req['next_number'] = 10
    self.call_api('set_next_build_number', req, status=400)
    self.assertEqual(seq.key.get().next_number, 20)

    req['builder'] = 'does not exist'
    self.call_api('set_next_build_number', req, status=400)
