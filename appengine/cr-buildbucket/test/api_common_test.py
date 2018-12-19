# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json

from components import utils
utils.fix_protobuf_package()

from google.protobuf import struct_pb2

from test import config_test
from testing_utils import testing

import api_common
import config
import model


class ApiCommonTests(testing.AppengineTestCase):

  def setUp(self):
    super(ApiCommonTests, self).setUp()
    self.patch(
        'components.utils.utcnow', return_value=datetime.datetime(2017, 1, 1)
    )
    self.test_build = model.Build(
        id=1,
        bucket_id='chromium/try',
        create_time=datetime.datetime(2017, 1, 1),
        parameters={
            model.BUILDER_PARAMETER: 'linux_rel',
        },
        input_properties=struct_pb2.Struct(),
        canary_preference=model.CanaryPreference.AUTO,
        swarming_hostname='swarming.example.com',
    )

  def test_expired_build_to_message(self):
    yesterday = utils.utcnow() - datetime.timedelta(days=1)
    yesterday_timestamp = utils.datetime_to_timestamp(yesterday)
    self.test_build.lease_key = 1
    self.test_build.lease_expiration_date = yesterday
    msg = api_common.build_to_message(self.test_build)
    self.assertEqual(msg.lease_expiration_ts, yesterday_timestamp)

  def test_build_to_dict_empty(self):
    expected = {
        'project':
            'chromium',
        'bucket':
            'luci.chromium.try',
        'created_ts':
            '1483228800000000',
        'id':
            '1',
        'parameters_json':
            json.dumps(
                {
                    model.BUILDER_PARAMETER: 'linux_rel',
                    model.PROPERTIES_PARAMETER: {},
                },
                sort_keys=True,
            ),
        'result_details_json':
            'null',
        'status':
            'SCHEDULED',
        'tags': [],
        'utcnow_ts':
            '1483228800000000',
        'canary_preference':
            'AUTO',
    }
    self.assertEqual(expected, api_common.build_to_dict(self.test_build))

  def test_build_to_dict_non_luci(self):
    self.test_build.bucket_id = 'chromium/master.chromium'
    self.test_build.swarming_hostname = None

    actual = api_common.build_to_dict(self.test_build)
    self.assertEqual(actual['project'], 'chromium')
    self.assertEqual(actual['bucket'], 'master.chromium')

  def test_build_to_dict_full(self):
    self.test_build.start_time = datetime.datetime(2017, 1, 2)
    self.test_build.complete_time = datetime.datetime(2017, 1, 2)
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.result_details = {'result': 'nice'}
    self.test_build.service_account = 'robot@example.com'
    expected = {
        'project':
            'chromium',
        'bucket':
            'luci.chromium.try',
        'completed_ts':
            '1483315200000000',
        'created_ts':
            '1483228800000000',
        'id':
            '1',
        'parameters_json':
            json.dumps(
                {
                    model.BUILDER_PARAMETER: 'linux_rel',
                    model.PROPERTIES_PARAMETER: {},
                },
                sort_keys=True,
            ),
        'result':
            'SUCCESS',
        'result_details_json':
            json.dumps({'result': 'nice'}),
        'started_ts':
            '1483315200000000',
        'status':
            'COMPLETED',
        'tags': [],
        'utcnow_ts':
            '1483228800000000',
        'canary_preference':
            'AUTO',
        'service_account':
            'robot@example.com',
    }
    self.assertEqual(expected, api_common.build_to_dict(self.test_build))

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
        config_test.parse_bucket_cfg('name: "luci.chromium.try"'),
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
