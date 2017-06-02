# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json

from components import utils

from testing_utils import testing

import api_common
import model


class ApiCommonTests(testing.AppengineTestCase):
  def setUp(self):
    super(ApiCommonTests, self).setUp()
    self.patch(
        'components.utils.utcnow', return_value=datetime.datetime(2017, 1, 1))
    self.test_build = model.Build(
        id=1,
        bucket='chromium',
        create_time=datetime.datetime(2017, 1, 1),
        parameters={
          'buildername': 'linux_rel',
        },
    )

  def test_expired_build_to_message(self):
    yesterday = utils.utcnow() - datetime.timedelta(days=1)
    yesterday_timestamp = utils.datetime_to_timestamp(yesterday)
    self.test_build.lease_key = 1
    self.test_build.lease_expiration_date = yesterday
    msg = api_common.build_to_message(self.test_build)
    self.assertEqual(msg.lease_expiration_ts, yesterday_timestamp)

  def test_build_to_dict(self):
    self.test_build.start_time = datetime.datetime(2017, 1, 2)
    self.test_build.complete_time = datetime.datetime(2017, 1, 2)
    self.test_build.status = model.BuildStatus.COMPLETED
    self.test_build.result = model.BuildResult.SUCCESS
    self.test_build.result_details = {'result': 'nice'}
    expected = {
      'bucket': 'chromium',
      'completed_ts': '1483315200000000',
      'created_ts': '1483228800000000',
      'id': '1',
      'parameters_json': json.dumps({'buildername': 'linux_rel'}),
      'result': 'SUCCESS',
      'result_details_json': json.dumps({'result': 'nice'}),
      'started_ts': '1483315200000000',
      'status': 'COMPLETED',
      'tags': [],
      'utcnow_ts': '1483228800000000',
    }
    self.assertEqual(expected, api_common.build_to_dict(self.test_build))
