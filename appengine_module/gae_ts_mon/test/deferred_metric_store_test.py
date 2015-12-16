# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import operator
import unittest

import gae_ts_mon
import mock

from google.appengine.ext import testbed
from google.appengine.api.memcache import memcache_service_pb

from infra_libs.ts_mon import deferred_metric_store
from infra_libs.ts_mon import memcache_metric_store
from infra_libs.ts_mon.common import errors
from infra_libs.ts_mon.common import metric_store
from infra_libs.ts_mon.common import metrics
from infra_libs.ts_mon.common import targets
from infra_libs.ts_mon.common.test import metric_store_test
from testing_utils import testing


class DeferredMetricStoreTest(metric_store_test.MetricStoreTestBase,
                              testing.AppengineTestCase):
  def setUp(self):
    super(DeferredMetricStoreTest, self).setUp()

    self.counter_metric = metrics.CounterMetric('test/counter')
    self.cumulative_metric = metrics.CumulativeMetric('test/cumulative')
    self.cumulative_dist_metric = metrics.CumulativeDistributionMetric(
        'test/cumulative_dist')
    self.str_metric = metrics.StringMetric('test/str')
    self.gauge_metric = metrics.GaugeMetric('test/gauge')
    self.dist_metric = metrics.NonCumulativeDistributionMetric('test/dist')

    self.state.target = targets.TaskTarget('myapp', 'mymodule', 'appengine', '')
    self.store.update_metric_index()

  def create_store(self, state, **kwargs):
    kwargs['time_fn'] = self.mock_time
    self.base_store = memcache_metric_store.MemcacheMetricStore(state, **kwargs)
    return deferred_metric_store.DeferredMetricStore(
        state, self.base_store, **kwargs)

  def test_deferred_set(self):
    self.store.initialize_context()

    self.gauge_metric.set(123)
    self.assertIsNone(self.gauge_metric.get())

    self.store.finalize_context()
    self.assertEquals(123, self.gauge_metric.get())

  def test_deferred_incr(self):
    self.store.initialize_context()

    self.counter_metric.increment()
    self.assertIsNone(self.counter_metric.get())

    self.store.finalize_context()
    self.assertEquals(1, self.counter_metric.get())

  def test_finalize_without_initialize(self):
    with self.assertRaises(
        deferred_metric_store.FinalizeWithoutInitializeError):
      self.store.finalize_context()

  def test_deferred_reset_for_unittest(self):
    self.store.initialize_context()
    self.counter_metric.increment()
    self.store.reset_for_unittest()
    self.store.finalize_context()

    self.assertIsNone(self.counter_metric.get())

  def test_deferred_reset_for_unittest_with_name(self):
    self.store.initialize_context()
    self.counter_metric.increment()
    self.store.reset_for_unittest(name=self.counter_metric.name)
    self.store.finalize_context()

    self.assertIsNone(self.counter_metric.get())

  def test_deferred_reset_for_unittest_with_other_name(self):
    self.store.initialize_context()
    self.counter_metric.increment()
    self.store.reset_for_unittest(name='something_else')
    self.store.finalize_context()

    self.assertEquals(1, self.counter_metric.get())

  def test_deferred_set_then_incr(self):
    self.store.initialize_context()
    self.counter_metric.set(42)
    self.counter_metric.increment()
    self.store.finalize_context()

    self.assertEquals(43, self.counter_metric.get())

  def test_deferred_incr_then_incr(self):
    self.store.initialize_context()
    self.counter_metric.increment()
    self.counter_metric.increment()
    self.store.finalize_context()

    self.assertEquals(2, self.counter_metric.get())

  def test_deferred_incr_then_set(self):
    self.store.initialize_context()
    self.counter_metric.increment()
    self.counter_metric.set(42)
    self.store.finalize_context()

    self.assertEquals(42, self.counter_metric.get())

  def test_deferred_set_then_set(self):
    self.store.initialize_context()
    self.counter_metric.set(42)
    self.counter_metric.set(12)
    self.store.finalize_context()

    self.assertEquals(12, self.counter_metric.get())

  def test_deferred_set_with_fields(self):
    self.store.initialize_context()
    self.gauge_metric.set(41, {'f': 1})
    self.gauge_metric.set(42, {'f': 2})
    self.store.finalize_context()

    self.assertEqual(41, self.gauge_metric.get({'f': 1}))
    self.assertEqual(42, self.gauge_metric.get({'f': 2}))

  def test_deferred_distribution_incr(self):
    self.store.initialize_context()
    self.cumulative_dist_metric.add(6)
    self.store.finalize_context()

    self.assertEquals(6, self.cumulative_dist_metric.get().sum)

  def test_deferred_distribution_incr_then_incr(self):
    self.store.initialize_context()
    self.cumulative_dist_metric.add(4)
    self.cumulative_dist_metric.add(1)
    self.store.finalize_context()

    self.assertEquals(5, self.cumulative_dist_metric.get().sum)
