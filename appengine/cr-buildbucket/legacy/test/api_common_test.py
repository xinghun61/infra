# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock

from components import utils
utils.fix_protobuf_package()

from test import test_util
from testing_utils import testing

from legacy import api_common
from proto import common_pb2
from proto import service_config_pb2
import bbutil
import config
import model


class ApiCommonTests(testing.AppengineTestCase):

  maxDiff = None

  def setUp(self):
    super(ApiCommonTests, self).setUp()
    self.patch(
        'components.utils.utcnow', return_value=datetime.datetime(2017, 1, 1)
    )

  def test_expired_build_to_message(self):
    yesterday = utils.utcnow() - datetime.timedelta(days=1)
    yesterday_timestamp = utils.datetime_to_timestamp(yesterday)
    build = test_util.build()
    build.lease_key = 1
    build.lease_expiration_date = yesterday
    msg = api_common.build_to_message(build, None)
    self.assertEqual(msg.lease_expiration_ts, yesterday_timestamp)

  def test_build_to_dict(self):
    params_json = json.dumps(
        {
            model.BUILDER_PARAMETER: 'linux',
            model.PROPERTIES_PARAMETER: {'build-defined-property': 1.0,},
        },
        sort_keys=True,
    )
    tags = [
        'build_address:luci.chromium.try/linux/1',
        'builder:linux',
        'buildset:1',
        'swarming_hostname:swarming.example.com',
        (
            'swarming_tag:log_location:'
            'logdog://logdog.example.com/chromium/bb/+/annotations'
        ),
        'swarming_tag:luci_project:chromium',
        'swarming_tag:os:Ubuntu',
        'swarming_tag:recipe_name:recipe',
        'swarming_tag:recipe_package:infra/recipe_bundle',
        'swarming_task_id:deadbeef',
    ]
    result_details = {
        'properties': {'a': 'b'},
        'swarming': {
            'bot_dimensions': {
                'dim1': ['v1', 'v2'],
                'os': ['Ubuntu'],
            },
        },
        'error': {'message': 'bad'},
        'ui': {'info': 'bad'},
    }
    expected = {
        'project': 'chromium',
        'bucket': 'luci.chromium.try',
        'created_by': 'anonymous:anonymous',
        'created_ts': '1483228800000000',
        'experimental': False,
        'completed_ts': '1483228800000000',
        'id': '8991715593768927232',
        'parameters_json': params_json,
        'result_details_json': json.dumps(result_details, sort_keys=True),
        'status': 'COMPLETED',
        'result': 'FAILURE',
        'failure_reason': 'INFRA_FAILURE',
        'status_changed_ts': '1483228800000000',
        'tags': tags,
        'utcnow_ts': '1483228800000000',
        'updated_ts': '1483228800000000',
        'canary_preference': 'PROD',
        'canary': False,
        'service_account': 'service@example.com',
        'url': 'https://ci.example.com/8991715593768927232',
    }

    out_props = model.BuildOutputProperties()
    out_props.serialize(bbutil.dict_to_struct({'a': 'b'}))
    build = test_util.build(
        status=common_pb2.INFRA_FAILURE,
        summary_markdown='bad',
        input=dict(
            properties=bbutil.dict_to_struct({
                'recipe': 'recipe',
                'build-defined-property': 1,
                'builder-defined-property': 2,
            })
        ),
        infra=dict(
            swarming=dict(
                bot_dimensions=[
                    dict(key='dim1', value='v1'),
                    dict(key='dim1', value='v2'),
                    dict(key='os', value='Ubuntu'),
                ],
            ),
            buildbucket=dict(
                requested_properties=bbutil.dict_to_struct({
                    'build-defined-property': 1,
                }),
            ),
        ),
    )
    self.assertEqual(
        expected,
        test_util.ununicode(api_common.build_to_dict(build, out_props))
    )

  def test_build_to_dict_non_luci(self):
    build = test_util.build(builder=dict(bucket='master.chromium'))
    build.is_luci = False

    actual = api_common.build_to_dict(build, None)
    self.assertEqual(actual['project'], 'chromium')
    self.assertEqual(actual['bucket'], 'master.chromium')

  def test_format_luci_bucket(self):
    self.assertEqual(
        api_common.format_luci_bucket('chromium/try'), 'luci.chromium.try'
    )

  def test_parse_luci_bucket(self):
    self.assertEqual(
        api_common.parse_luci_bucket('luci.chromium.try'), 'chromium/try'
    )
    self.assertEqual(api_common.parse_luci_bucket('master.x'), '')


class ToBucketIDTest(testing.AppengineTestCase):

  def setUp(self):
    super(ToBucketIDTest, self).setUp()

    config.put_bucket(
        'chromium',
        'a' * 40,
        test_util.parse_bucket_cfg('name: "luci.chromium.try"'),
    )

  def to_bucket_id(self, bucket):
    return api_common.to_bucket_id_async(bucket).get_result()

  def test_convert_bucket_native(self):
    self.assertEqual(self.to_bucket_id('chromium/try'), 'chromium/try')

  def test_convert_bucket_luci(self):
    self.assertEqual(self.to_bucket_id('luci.chromium.try'), 'chromium/try')

  def test_convert_bucket_resolution(self):
    self.assertEqual(self.to_bucket_id('try'), 'chromium/try')

  def test_convert_bucket_resolution_fails(self):
    self.assertIsNone(self.to_bucket_id('master.x'))

  def test_get_build_url(self):
    build = test_util.build(id=1)
    self.assertEqual(
        api_common.get_build_url(build), 'https://ci.example.com/1'
    )

  @mock.patch('config.get_settings_async')
  def test_get_build_url_milo(self, get_settings_async):
    get_settings_async.return_value = test_util.future(
        service_config_pb2.SettingsCfg(
            swarming=dict(milo_hostname='milo.example.com')
        ),
    )

    build = test_util.build(id=1)
    build.url = None
    self.assertEqual(
        api_common.get_build_url(build), 'https://milo.example.com/b/1'
    )


class PropertiesToJson(testing.AppengineTestCase):

  def test_basic(self):
    expected = json.dumps(
        {
            'a': 'b',
            'buildnumber': 1,
            'another number': 1.0,
        },
        sort_keys=True,
    )

    actual = api_common.properties_to_json({
        'a': 'b',
        'buildnumber': 1,
        'another number': 1,
    })
    self.assertEqual(expected, actual)
