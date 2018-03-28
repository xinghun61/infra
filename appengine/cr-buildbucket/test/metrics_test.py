# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from google.appengine.ext import ndb
import mock
import gae_ts_mon

from testing_utils import testing
from proto import project_config_pb2
from test.test_util import future
import metrics
import model


class MetricsTest(testing.AppengineTestCase):
  def setUp(self):
    super(MetricsTest, self).setUp()
    gae_ts_mon.reset_for_unittest(disable=True)

  def test_set_build_count_metric(self):
    ndb.put_multi([
      model.Build(
          bucket='chromium',
          status=model.BuildStatus.SCHEDULED,
          create_time=datetime.datetime(2015, 1, 1),
          tags=['builder:release'],
          experimental=True,
      ),
      model.Build(
          bucket='chromium',
          status=model.BuildStatus.SCHEDULED,
          tags=['builder:release'],
          create_time=datetime.datetime(2015, 1, 1),
      ),
      model.Build(
          bucket='chromium',
          status=model.BuildStatus.SCHEDULED,
          tags=['builder:release'],
          create_time=datetime.datetime(2015, 1, 1),
      ),
      model.Build(
          bucket='chromium',
          status=model.BuildStatus.SCHEDULED,
          tags=['builder:debug'],
          create_time=datetime.datetime(2015, 1, 1),
      ),
      model.Build(
          bucket='v8',
          status=model.BuildStatus.SCHEDULED,
          create_time=datetime.datetime(2015, 1, 1),
      ),
      model.Build(
          bucket='chromium',
          status=model.BuildStatus.STARTED,
          create_time=datetime.datetime(2015, 1, 1),
          start_time=datetime.datetime(2015, 1, 1),
      ),
    ])
    metrics.set_build_count_metric_async(
        'chromium',
        'release',
        model.BuildStatus.SCHEDULED,
        False).get_result()
    self.assertEqual(2, metrics.BUILD_COUNT_PROD.get(
        {'bucket': 'chromium', 'builder': 'release', 'status': 'SCHEDULED'},
        target_fields=metrics.GLOBAL_TARGET_FIELDS))

  @mock.patch('components.utils.utcnow', autospec=True)
  def test_set_build_lease_latency(self, utcnow):
    utcnow.return_value = datetime.datetime(2015, 1, 4)

    ndb.put_multi([
      model.Build(
          bucket='chromium',
          status=model.BuildStatus.SCHEDULED,
          never_leased=True,
          create_time=datetime.datetime(2014, 1, 1),
          experimental=True,
      ),
      model.Build(
          bucket='chromium',
          status=model.BuildStatus.SCHEDULED,
          never_leased=True,
          create_time=datetime.datetime(2015, 1, 1),
      ),
      model.Build(
          bucket='chromium',
          status=model.BuildStatus.SCHEDULED,
          never_leased=True,
          create_time=datetime.datetime(2015, 1, 3),
      ),
      model.Build(
          bucket='chromium',
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.CANCELED,
          cancelation_reason=model.CancelationReason.TIMEOUT,
          never_leased=True,
          create_time=datetime.datetime(2015, 1, 3),
          complete_time=datetime.datetime(2015, 1, 4),
          canary=False,
      ),
      model.Build(
          bucket='chromium',
          status=model.BuildStatus.SCHEDULED,
          create_time=datetime.datetime(2015, 1, 3),
      ),
      model.Build(
          bucket='v8',
          status=model.BuildStatus.SCHEDULED,
          never_leased=True,
          create_time=datetime.datetime(2015, 1, 3),
      ),
    ])
    metrics.set_build_latency(
        metrics.LEASE_LATENCY_SEC, 'chromium', True).get_result()
    metrics.set_build_latency(
        metrics.START_LATENCY_SEC, 'chromium', False).get_result()
    dist = metrics.LEASE_LATENCY_SEC.get(
        {'bucket': 'chromium'},
        target_fields=metrics.GLOBAL_TARGET_FIELDS)
    self.assertEquals(dist.sum, 4.0 * 24 * 3600)  # 4 days
    dist = metrics.START_LATENCY_SEC.get(
        {'bucket': 'chromium'},
        target_fields=metrics.GLOBAL_TARGET_FIELDS)
    self.assertEquals(dist.sum, 4.0 * 24 * 3600)  # 4 days

  @mock.patch('config.get_buckets_async', autospec=True)
  @mock.patch('metrics.set_build_latency', autospec=True)
  @mock.patch('metrics.set_build_count_metric_async', autospec=True)
  def test_update_global_metrics(
      self, set_build_count_metric_async, set_build_latency,
      get_buckets_async):
    get_buckets_async.return_value = future([
      project_config_pb2.Bucket(name='x')
    ])

    model.Builder(id='chromium:luci.chromium.try:release').put()
    model.Builder(id='chromium:luci.chromium.try:debug').put()

    metrics.update_global_metrics()

    set_build_latency.assert_any_call(
        metrics.LEASE_LATENCY_SEC, 'x', True)
    set_build_latency.assert_any_call(
        metrics.START_LATENCY_SEC, 'x', False)

    set_build_count_metric_async.assert_any_call(
        'luci.chromium.try', 'release', model.BuildStatus.SCHEDULED, False)
    set_build_count_metric_async.assert_any_call(
        'luci.chromium.try', 'release', model.BuildStatus.SCHEDULED, True)
    set_build_count_metric_async.assert_any_call(
        'luci.chromium.try', 'debug', model.BuildStatus.SCHEDULED, False)
    set_build_count_metric_async.assert_any_call(
        'luci.chromium.try', 'debug', model.BuildStatus.SCHEDULED, True)

  def test_fields_for(self):
    build = model.Build(
        bucket='master.x',
        tags=[
          'builder:release',
          'user_agent:cq',
          'something:else',
        ],
        status=model.BuildStatus.COMPLETED,
        result=model.BuildResult.FAILURE,
        failure_reason=model.FailureReason.BUILD_FAILURE,
        canary=True,
    )
    expected = {
      'bucket': 'master.x',
      'builder': 'release',
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
