# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import random
import unittest

import gae_ts_mon
import mock

from google.appengine.ext import testbed
from google.appengine.api.memcache import memcache_service_pb

from infra_libs.ts_mon import memcache_metric_store
from infra_libs.ts_mon.common import errors
from infra_libs.ts_mon.common import interface
from infra_libs.ts_mon.common import metric_store
from infra_libs.ts_mon.common import metrics
from infra_libs.ts_mon.common import targets
from infra_libs.ts_mon.common.test import metric_store_test
from testing_utils import testing


class MemcacheMetricStoreTest(metric_store_test.MetricStoreTestBase,
                              testing.AppengineTestCase):
  METRIC_STORE_CLASS = memcache_metric_store.MemcacheMetricStore

  def setUp(self):
    super(MemcacheMetricStoreTest, self).setUp()

    self.counter_metric = metrics.CounterMetric('test/counter')
    self.cumulative_metric = metrics.CumulativeMetric('test/cumulative')
    self.cumulative_dist_metric = metrics.CumulativeDistributionMetric(
        'test/cumulative_dist')
    self.str_metric = metrics.StringMetric('test/str')
    self.gauge_metric = metrics.GaugeMetric('test/gauge')
    self.dist_metric = metrics.NonCumulativeDistributionMetric('test/dist')

    self.state.target = targets.TaskTarget('myapp', 'mymodule', 'appengine', '')
    self.store.update_metric_index()

  def test_compare_and_set_failed(self):
    def fake_set(request, response):
      response.add_set_status(memcache_service_pb.MemcacheSetResponse.ERROR)

    interface.register(memcache_metric_store.cas_failures)

    memcache_stub = self.testbed.get_stub(testbed.MEMCACHE_SERVICE_NAME)
    memcache_stub._Dynamic_Set = fake_set

    self.store.set('foo', (('field', 'value'),), 42)

    self.assertIsNone(self.store.get('foo', (('field', 'value'),)))

  def test_report_module_versions(self):
    self.store.report_module_versions = True
    all_metrics = list(self.store.get_all())
    self.assertEqual(1, len(all_metrics))
    self.assertEqual('default', all_metrics[0][0].job_name)
    self.assertEqual('appengine/default_version', all_metrics[0][1].name)
    self.assertEqual({(): '1'}, all_metrics[0][3])

  def test_rejects_set_magical_metrics(self):
    with self.assertRaises(errors.MonitoringError):
      self.store.set('appengine/default_version', ((),), 'blah')

  def test_counters_are_sharded(self):
    self.assertTrue(self.store._is_metric_sharded(self.counter_metric))
    self.assertTrue(self.store._is_metric_sharded(self.cumulative_metric))
    self.assertTrue(self.store._is_metric_sharded(self.cumulative_dist_metric))
    self.assertFalse(self.store._is_metric_sharded(self.str_metric))
    self.assertFalse(self.store._is_metric_sharded(self.gauge_metric))
    self.assertFalse(self.store._is_metric_sharded(self.dist_metric))

  def test_all_shards(self):
    self.assertEquals(
        memcache_metric_store.MemcacheMetricStore.SHARDS_PER_METRIC,
        len(self.store._all_shards(self.counter_metric)))
    self.assertEquals(
        memcache_metric_store.MemcacheMetricStore.SHARDS_PER_METRIC,
        len(self.store._all_shards(self.cumulative_metric)))
    self.assertEquals(
        memcache_metric_store.MemcacheMetricStore.SHARDS_PER_METRIC,
        len(self.store._all_shards(self.cumulative_dist_metric)))
    self.assertEquals(1, len(self.store._all_shards(self.str_metric)))
    self.assertEquals(1, len(self.store._all_shards(self.gauge_metric)))
    self.assertEquals(1, len(self.store._all_shards(self.dist_metric)))

  def test_random_shard_counter(self):
    select_shard = mock.create_autospec(random.randint, return_value=4)
    shards = set(self.store._all_shards(self.counter_metric))
    self.assertIn(self.store._random_shard(
        self.counter_metric, select_shard=select_shard), shards)

    select_shard.assert_called_once_with(
        1, memcache_metric_store.MemcacheMetricStore.SHARDS_PER_METRIC)

  def test_random_shard_gauge(self):
    select_shard = mock.create_autospec(random.randint, return_value=4)
    self.assertEqual(
        self.gauge_metric.name,
        self.store._random_shard(self.gauge_metric, select_shard=select_shard))

    self.assertFalse(select_shard.called)

  def test_incr_sharded(self):
    for _ in xrange(10000):
      self.store.incr(self.counter_metric.name, (), 1)

    client = self.store._client()
    namespace = self.store._namespace_for_job()

    self.assertIsNone(client.get(self.counter_metric.name, namespace=namespace))
    for shard in self.store._all_shards(self.counter_metric):
      self.assertIsNotNone(client.get(shard, namespace=namespace))

  def test_get_sharded_sum(self):
    for _ in xrange(10000):
      self.store.incr(self.counter_metric.name, (), 1)
    self.assertEquals(10000, self.store.get(self.counter_metric.name, ()))

  def test_get_all_sharded(self):
    for _ in xrange(10000):
      self.store.incr(self.counter_metric.name, (), 1)

    task_numbers = []
    values = []
    for target, metric, start_time, field_values in self.store.get_all():
      task_numbers.append(target.task_num)
      values.append(field_values[()])

    self.assertEqual(
        range(memcache_metric_store.MemcacheMetricStore.SHARDS_PER_METRIC),
        sorted(task_numbers))
    self.assertEqual(10000, sum(values))

  def test_get_sharded_distribution(self):
    for _ in xrange(10000):
      self.cumulative_dist_metric.add(1)

    with self.assertRaises(TypeError):
      self.store.get(self.cumulative_dist_metric.name, ())

  def test_modify_multi_set(self):
    self.store.modify_multi([
        metric_store.Modification(
            self.str_metric.name, (), 'set', ('foo', False)),
        metric_store.Modification(
            self.gauge_metric.name, (), 'set', (123, False))])

    self.assertEqual('foo', self.str_metric.get())
    self.assertEqual(123, self.gauge_metric.get())

  def test_modify_multi_set_negative(self):
    self.gauge_metric.set(42)

    with self.assertRaises(errors.MonitoringDecreasingValueError):
      self.store.modify_multi([
          metric_store.Modification(
              self.gauge_metric.name, (), 'set', (41, True))])

  def test_modify_multi_incr(self):
    self.gauge_metric.set(42)

    self.store.modify_multi([
        metric_store.Modification(
            self.gauge_metric.name, (), 'incr', (4, None))])

    self.assertEqual(46, self.gauge_metric.get())

  def test_modify_multi_incr_negative(self):
    with self.assertRaises(errors.MonitoringDecreasingValueError):
      self.store.modify_multi([
          metric_store.Modification(
              self.gauge_metric.name, (), 'incr', (-1, None))])

  def test_modify_multi_bad_type(self):
    with self.assertRaises(errors.UnknownModificationTypeError):
      self.store.modify_multi([
          metric_store.Modification(
              self.gauge_metric.name, (), 'bad', (-1, None))])

  def test_modify_multi_with_fields(self):
    self.store.modify_multi([
        metric_store.Modification(
            self.gauge_metric.name, (('f', 1),), 'set', (41, False)),
        metric_store.Modification(
            self.gauge_metric.name, (('f', 2),), 'set', (42, False))])

    self.assertEqual(41, self.gauge_metric.get({'f': 1}))
    self.assertEqual(42, self.gauge_metric.get({'f': 2}))
