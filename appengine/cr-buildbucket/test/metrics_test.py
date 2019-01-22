# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

import mock
import gae_ts_mon

from test import test_util
from test.test_util import future
from testing_utils import testing
from proto import common_pb2
import config
import metrics
import model


class MetricsTest(testing.AppengineTestCase):

  def setUp(self):
    super(MetricsTest, self).setUp()
    gae_ts_mon.reset_for_unittest(disable=True)

  def test_set_build_count_metric(self):

    def mkbuild(
        bucket='try',
        builder='release',
        status=common_pb2.SCHEDULED,
        experimental=False
    ):
      test_util.build(
          builder=dict(project='chromium', bucket=bucket, builder=builder),
          status=status,
          input=dict(experimental=experimental),
      ).put()

    mkbuild()
    mkbuild()
    mkbuild(builder='debug')
    mkbuild(bucket='ci')
    mkbuild(status=common_pb2.STARTED)
    mkbuild(experimental=True)

    metrics.set_build_count_metric_async(
        'chromium/try', 'luci.chromium.try', 'release',
        model.BuildStatus.SCHEDULED, False
    ).get_result()
    self.assertEqual(
        2,
        metrics.BUILD_COUNT_PROD.get({
            'bucket': 'luci.chromium.try',
            'builder': 'release',
            'status': 'SCHEDULED',
        },
                                     target_fields=metrics.GLOBAL_TARGET_FIELDS)
    )

  @mock.patch('components.utils.utcnow', autospec=True)
  def test_set_build_lease_latency(self, utcnow):
    utcnow.return_value = datetime.datetime(2015, 1, 4)

    def mkbuild(
        create_time,
        never_leased,
        bucket='try',
        status=common_pb2.SCHEDULED,
        experimental=False
    ):
      build = test_util.build(
          builder=dict(project='chromium', bucket=bucket, builder='release'),
          status=status,
          create_time=test_util.dt2ts(create_time),
          input=dict(experimental=experimental),
      )
      build.never_leased = never_leased
      build.put()

    mkbuild(datetime.datetime(2014, 12, 31), False)  # oldest
    mkbuild(datetime.datetime(2015, 1, 1), True)  # oldest never leased
    mkbuild(datetime.datetime(2015, 1, 3), True)
    mkbuild(datetime.datetime(2014, 1, 1), True, experimental=True)
    mkbuild(
        datetime.datetime(2015, 1, 3), True, status=common_pb2.INFRA_FAILURE
    )
    # never_leased is None, so this should be ignored by both metrics.
    mkbuild(datetime.datetime(2014, 1, 3), None)
    mkbuild(datetime.datetime(2015, 1, 3), True, bucket='ci')

    metrics.set_build_latency(
        'chromium/try', 'luci.chromium.try', 'release', True
    ).get_result()
    metrics.set_build_latency(
        'chromium/try', 'luci.chromium.try', 'release', False
    ).get_result()
    max_lease = metrics.MAX_AGE_SCHEDULED.get(
        {
            'bucket': 'luci.chromium.try',
            'builder': 'release',
            'must_be_never_leased': True,
        },
        target_fields=metrics.GLOBAL_TARGET_FIELDS,
    )
    self.assertEqual(max_lease, 3 * 24 * 3600)
    max_start = metrics.MAX_AGE_SCHEDULED.get(
        {
            'bucket': 'luci.chromium.try',
            'builder': 'release',
            'must_be_never_leased': False,
        },
        target_fields=metrics.GLOBAL_TARGET_FIELDS,
    )
    self.assertEqual(max_start, 4 * 24 * 3600)

  def test_set_build_lease_latency_no_pending_builds(self):
    metrics.set_build_latency(
        'chromium/try', 'luci.chromium.try', 'release', True
    ).get_result()
    metrics.set_build_latency(
        'chromium/try', 'luci.chromium.try', 'release', False
    ).get_result()
    max_lease = metrics.MAX_AGE_SCHEDULED.get(
        {
            'bucket': 'luci.chromium.try',
            'builder': 'release',
            'must_be_never_leased': True,
        },
        target_fields=metrics.GLOBAL_TARGET_FIELDS,
    )
    self.assertEqual(max_lease, 0)
    max_start = metrics.MAX_AGE_SCHEDULED.get(
        {
            'bucket': 'luci.chromium.try',
            'builder': 'release',
            'must_be_never_leased': False,
        },
        target_fields=metrics.GLOBAL_TARGET_FIELDS,
    )
    self.assertEqual(max_start, 0)

  @mock.patch('metrics.set_build_latency', autospec=True)
  @mock.patch('metrics.set_build_count_metric_async', autospec=True)
  def test_update_global_metrics(
      self, set_build_count_metric_async, set_build_latency
  ):
    set_build_count_metric_async.return_value = future(None)
    set_build_latency.return_value = future(None)

    model.Builder(id='chromium:luci.chromium.try:release').put()
    model.Builder(id='chromium:luci.chromium.try:debug').put()
    model.Builder(id='chromium:try:debug').put()
    config.put_bucket(
        'chromium',
        'a' * 40,
        test_util.parse_bucket_cfg(
            '''
          name: "luci.chromium.try"
          swarming {
            builders {}
          }
          '''
        ),
    )

    metrics.update_global_metrics()

    set_build_latency.assert_any_call(
        'chromium/try', 'luci.chromium.try', 'release', True
    )
    set_build_latency.assert_any_call(
        'chromium/try', 'luci.chromium.try', 'release', False
    )
    set_build_latency.assert_any_call(
        'chromium/try', 'luci.chromium.try', 'debug', True
    )
    set_build_latency.assert_any_call(
        'chromium/try', 'luci.chromium.try', 'debug', False
    )

    set_build_count_metric_async.assert_any_call(
        'chromium/try', 'luci.chromium.try', 'release',
        model.BuildStatus.SCHEDULED, False
    )
    set_build_count_metric_async.assert_any_call(
        'chromium/try', 'luci.chromium.try', 'release',
        model.BuildStatus.SCHEDULED, True
    )
    set_build_count_metric_async.assert_any_call(
        'chromium/try', 'luci.chromium.try', 'debug',
        model.BuildStatus.SCHEDULED, False
    )
    set_build_count_metric_async.assert_any_call(
        'chromium/try', 'luci.chromium.try', 'debug',
        model.BuildStatus.SCHEDULED, True
    )

  def test_fields_for(self):
    build = test_util.build(
        builder=dict(project='chromium', bucket='try', builder='linux'),
        status=common_pb2.FAILURE,
        tags=[
            dict(key='user_agent', value='cq'),
            dict(key='something', value='else'),
        ],
        infra=dict(buildbucket=dict(canary=True)),
    )
    expected = {
        'bucket': 'luci.chromium.try',
        'builder': 'linux',
        'canary': True,
        'user_agent': 'cq',
        'status': 'COMPLETED',
        'result': 'FAILURE',
        'failure_reason': 'BUILD_FAILURE',
        'cancelation_reason': '',
    }
    self.assertEqual(set(expected), set(metrics._BUILD_FIELDS))
    actual = metrics._fields_for(build, expected.keys())
    self.assertEqual(expected, actual)

    with self.assertRaises(ValueError):
      metrics._fields_for(build, ['wrong field'])
