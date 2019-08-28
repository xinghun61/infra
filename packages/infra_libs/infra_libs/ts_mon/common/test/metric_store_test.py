# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import functools
import operator
import random
import threading
import time
import unittest

import mock

from infra_libs.ts_mon.common import distribution
from infra_libs.ts_mon.common import interface
from infra_libs.ts_mon.common import errors
from infra_libs.ts_mon.common import metric_store
from infra_libs.ts_mon.common import metrics
from infra_libs.ts_mon.common import targets
from infra_libs.ts_mon.common.test import my_target_pb2


class DefaultModifyFnTest(unittest.TestCase):

  def test_adds(self):
    fn = metric_store.default_modify_fn('foo')
    self.assertEquals(5, fn(2, 3))
    self.assertEquals(5, fn(3, 2))

  def test_negative(self):
    fn = metric_store.default_modify_fn('foo')
    with self.assertRaises(errors.MonitoringDecreasingValueError) as cm:
      fn(2, -1)
    self.assertIn('"foo"', str(cm.exception))


class MetricStoreTestBase(object):
  """Abstract base class for testing MetricStore implementations.

  This class doesn't inherit from unittest.TestCase to prevent it from being
  run automatically by expect_tests.

  Your subclass should inherit from this and unittest.TestCase, and set
  METRIC_STORE_CLASS to the implementation you want to test.  See
  InProcessMetricStoreTest in this file for an example.
  """

  METRIC_STORE_CLASS = None

  def setUp(self):
    super(MetricStoreTestBase, self).setUp()

    self.mock_time = mock.create_autospec(time.time, spec_set=True)
    self.mock_time.return_value = 1234

    target = targets.TaskTarget(
        'test_service', 'test_job', 'test_region', 'test_host')
    self.state = interface.State(store_ctor=self.create_store, target=target)
    mock.patch('infra_libs.ts_mon.common.interface.state',
        new=self.state).start()

    self.store = self.state.store

    self.metric = metrics.Metric('foo', 'desc', None)

  def create_store(self, *args, **kwargs):
    kwargs['time_fn'] = self.mock_time
    return self.METRIC_STORE_CLASS(*args, **kwargs)

  def tearDown(self):
    super(MetricStoreTestBase, self).tearDown()

    mock.patch.stopall()

  def test_sets_start_time(self):
    self.metric._start_time = None
    fields1 = tuple('value')
    start_time1 = 1234
    self.mock_time.return_value = start_time1
    self.store.set('foo', fields1, None, 42)

    fields2 = tuple('value2')
    start_time2 = 4321
    self.mock_time.return_value = start_time2
    self.store.set('foo', fields2, None, 43)

    all_metrics = list(self.store.get_all())
    self.assertEqual(1, len(all_metrics))
    self.assertEqual('foo', all_metrics[0][1].name)

    # the timestamps of both should be the same as their own.
    self.assertEqual(start_time1, all_metrics[0][2][fields1])
    self.assertEqual(start_time2, all_metrics[0][2][fields2])

  def test_start_time_remains_same(self):
    """Tests if the start_time of a stream remains the same after set()."""
    self.metric._start_time = None
    fields = tuple('value')
    initial_start_time = 7777

    for i in range(10):
      self.mock_time.return_value = initial_start_time + i
      self.store.set('foo', fields, None, 42 + i)
      all_metrics = list(self.store.get_all())

      self.assertEqual(1, len(all_metrics))
      self.assertEqual('foo', all_metrics[0][1].name)

      # the start_time should stay the same.
      self.assertEqual(initial_start_time, all_metrics[0][2][fields])

  def test_reset_resets_start_time(self):
    """Tests if the start_time of a stream remains the same after set()."""
    self.metric._start_time = None
    fields = tuple('value')
    initial_start_time = 7777
    reset_time = 8888
    value_set_time_after_reset = 9999

    # metrics were reported for the first time.
    self.mock_time.return_value = initial_start_time
    self.store.set('foo', fields, None, 42)
    all_metrics = list(self.store.get_all())
    self.assertEqual(1, len(all_metrics))
    self.assertEqual('foo', all_metrics[0][1].name)
    self.assertEqual(initial_start_time, all_metrics[0][2][fields])

    # metrics were reset.
    self.mock_time.return_value = reset_time
    self.store.reset_for_unittest()
    self.assertIsNone(self.store.get('foo', fields, None))

    # metrics were reported again.
    self.mock_time.return_value = value_set_time_after_reset
    self.store.set('foo', fields, None, 42)
    all_metrics = list(self.store.get_all())
    self.assertEqual(1, len(all_metrics))
    self.assertEqual('foo', all_metrics[0][1].name)
    self.assertEqual(value_set_time_after_reset, all_metrics[0][2][fields])

  def test_get(self):
    fields1 = ('value',)
    fields2 = ('value2',)
    fields3 = ('value3',)
    target_fields1 = {'region': 'rrr'}
    target_fields2 = {'region': 'rrr', 'hostname': 'hhh'}

    self.store.set('foo', fields1, None, 42)
    self.store.set('foo', fields2, None, 43)
    self.store.set('foo', fields1, target_fields1, 24)
    self.store.set('foo', fields2, target_fields2, 34)

    self.assertEquals(42, self.store.get('foo', fields1, None))
    self.assertEquals(43, self.store.get('foo', fields2, None))
    self.assertEquals(24, self.store.get('foo', fields1, target_fields1))
    self.assertEquals(34, self.store.get('foo', fields2, target_fields2))

    self.assertIsNone(self.store.get('foo', fields3, None))
    self.assertIsNone(self.store.get('foo', (), None))
    self.assertIsNone(self.store.get('foo', fields1, target_fields2))
    self.assertEquals(44, self.store.get('foo', fields3, None, default=44))

    self.assertIsNone(self.store.get('bar', (), None))

  def test_iter_field_values(self):
    fields1 = ('value',)
    fields2 = ('value2',)
    target_fields1 = {'region': 'rrr'}

    self.store.set('foo', fields1, None, 42)
    self.store.set('foo', fields2, None, 43)
    self.store.set('foo', fields2, target_fields1, 44)

    field_values = list(self.store.iter_field_values('foo'))
    self.assertEquals([
        (('value',), 42),
        (('value2',), 43),
        (('value2',), 44),
    ], sorted(field_values))

  def test_get_all(self):
    typ = my_target_pb2.MyTarget
    self.store.set('foo', ('bar',), typ(s='x'), 123)
    self.store.set('foo', ('bar',), typ(s='y'), 456)
    self.store.set('foo', ('qux',), typ(s='y'), 789)
    self.assertDictEqual({
        (my_target_pb2.MyTarget, False, 0, 'x'): {
            ('bar',): 123,
        },
        (my_target_pb2.MyTarget, False, 0, 'y'): {
            ('bar',): 456,
            ('qux',): 789,
        },
    }, {t[0]: t[4] for t in self.store.get_all()})

  def test_set(self):
    typ = my_target_pb2.MyTarget
    self.store.set('foo', ('value',), None, 12)
    self.store.set('foo', ('value',), typ(s='x'), 34)
    self.assertEqual(12, self.store.get('foo', ('value',), None))
    self.assertEqual(34, self.store.get('foo', ('value',), typ(s='x')))

  def test_set_enforce_ge(self):
    self.store.set('foo', ('value',), None, 42, enforce_ge=True)
    self.store.set('foo', ('value',), None, 43, enforce_ge=True)
    with self.assertRaises(errors.MonitoringDecreasingValueError):
      self.store.set('foo', ('value',), None, 42, enforce_ge=True)

  def test_incr(self):
    typ = my_target_pb2.MyTarget
    self.store.set('foo', ('value',), None, 42)
    self.store.set('foo', ('value',), typ(s='x'), 42)
    self.store.incr('foo', ('value',), None, 4)
    self.assertEquals(46, self.store.get('foo', ('value',), None))
    self.assertEquals(42, self.store.get('foo', ('value',), typ(s='x')))

  def test_incr_enforce_ge(self):
    with self.assertRaises(errors.MonitoringDecreasingValueError):
      self.store.incr('foo', ('value',), None, -1)

  def test_incr_modify_fn(self):
    def spec_fn(n, i): # pragma: no cover
      return n+i
    modify_fn = mock.create_autospec(spec_fn, spec_set=True)
    modify_fn.return_value = 7

    self.store.set('foo', ('value',), None, 42)
    self.store.incr('foo', ('value',), None, 3, modify_fn=modify_fn)

    self.assertEquals(7, self.store.get('foo', ('value',), None))
    modify_fn.assert_called_once_with(42, 3)

  def test_reset_for_unittest(self):
    self.store.set('foo', ('value',), None, 42)
    self.store.reset_for_unittest()
    self.assertIsNone(self.store.get('foo', ('value',), None))

  def test_reset_for_unittest_name(self):
    self.store.set('foo', ('value',), None, 42)
    self.store.reset_for_unittest(name='bar')
    self.assertEquals(42, self.store.get('foo', ('value',), None))

    self.store.reset_for_unittest(name='foo')
    self.assertIsNone(self.store.get('foo', ('value',), None))

  def test_unregister_metric(self):
    fields = (('field', 'value'),)
    self.store.set('foo', fields, None, 42)  # Registered in setUp().
    self.store.set('bar', fields, None, 24)  # Unregistered.
    all_metrics = list(self.store.get_all())
    self.assertEqual(1, len(all_metrics))
    self.assertEqual('foo', all_metrics[0][1].name)

  def test_copies_distributions(self):
    def modify_fn(dist, delta):
      # This is the same as the modify_fn in _DistributionMetricBase's add().
      if dist == 0:
        dist = distribution.Distribution(distribution.GeometricBucketer())
      dist.add(delta)
      return dist

    # Increment the metric once to create it in the store.
    self.store.incr('foo', (), None, 42, modify_fn)

    # Get its value from get_all.  We should get a copy of the distribution.
    dist = list(list(self.store.get_all())[0][4].iteritems())[0][1]
    self.assertEqual(1, dist.count)
    self.assertEqual(42, dist.sum)

    # Increment the metric again.
    self.store.incr('foo', (), None, 42, modify_fn)

    # The object we got should not change.
    self.assertEqual(1, dist.count)
    self.assertEqual(42, dist.sum)

  def test_get_all_thread_safe(self):
    """Dumb test to check that setting metrics while calling get_all is ok."""

    start = threading.Event()
    stop = threading.Event()

    def modify_worker():
      start.wait()
      while not stop.is_set():
        self.store.set('foo', (('field', random.random()),), None, 1)

    successful_workers = []
    def get_all_worker():
      start.wait()
      while not stop.is_set():
        for _, _, _, _, fields_values in self.store.get_all():
          list(fields_values.iteritems())
      successful_workers.append(True)

    # Create 10 modify threads and 10 get_all threads.
    threads = (
        [threading.Thread(target=modify_worker) for _ in xrange(10)] +
        [threading.Thread(target=get_all_worker) for _ in xrange(10)])

    # Start all the threads at once.
    for thread in threads:
      thread.start()
    start.set()

    # Wait 2 seconds then stop them all.
    time.sleep(2)
    stop.set()
    for thread in threads:
      thread.join()

    # All the threads should've been successful and not raised an exception in
    # get_all.
    self.assertEqual([True] * 10, successful_workers)


class InProcessMetricStoreTest(MetricStoreTestBase, unittest.TestCase):
  METRIC_STORE_CLASS = metric_store.InProcessMetricStore
