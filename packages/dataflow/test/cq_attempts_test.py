# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import apache_beam as beam
from dataflow import cq_attempts as job

from apache_beam.testing import test_pipeline
from apache_beam.testing import util
from dataflow.common import objects


class TestCQAttemptAccumulator(unittest.TestCase):
  def setUp(self):
    self.attempt_start_usec = 1493833887566000
    self.attempt_start_msec = self.attempt_start_usec / 1000
    self.timestamp_msec = 1493833887688
    self.earlier_timestamp = self.timestamp_msec - 1
    self.later_timestamp = self.timestamp_msec + 1
    self.combFn = job.CombineEventsToAttempt()

  def test_compute_attempts(self):
    complete_attempt_events = [
        {
            'timestamp_millis': 1,
            'action': self.combFn.ACTION_PATCH_START,
            'attempt_start_usec': 0,
            'cq_name': 'test_cq',
        },
        {
            'timestamp_millis': 2,
            'action': self.combFn.ACTION_PATCH_STOP,
            'attempt_start_usec': 0,
            'cq_name': 'test_cq',
        },
    ]
    complete_attempt_expected = [{
        'was_throttled': False,
        'waited_for_tree': False,
        'committed': False,
        'last_stop_msec': 2,
        'cq_name': 'test_cq',
        'last_start_msec': 1,
        'first_stop_msec': 2,
        'first_start_msec': 1,
        'attempt_start_msec': 0.0,
    }]
    incomplete_attempt_events = [
        {
            'timestamp_millis': 2,
            'action': self.combFn.ACTION_PATCH_START,
            'attempt_start_usec': 1,
            'cq_name': 'test_cq',
        },
    ]
    incomplete_attempt_expected = []
    events = complete_attempt_events + incomplete_attempt_events
    attempts = complete_attempt_expected + incomplete_attempt_expected

    p = test_pipeline.TestPipeline()
    pcoll = (p
             | beam.Create(events)
             | job.ComputeAttempts())
    util.assert_that(pcoll, util.equal_to(attempts))
    p.run()

  def basic_event(self, action=None, timestamp_millis=None,
                  attempt_start_usec=None, cq_name=None):
    event = objects.CQEvent()
    event.attempt_start_usec = (attempt_start_usec if attempt_start_usec else
                                self.attempt_start_usec)
    event.timestamp_millis = (timestamp_millis if timestamp_millis else
                              self.timestamp_msec)
    event.action = action if action else self.combFn.ACTION_PATCH_START
    event.cq_name = cq_name if cq_name else 'test_cq'
    return event

  def test_null_attempt_start_not_included(self):
    accumulator = self.combFn.add_input(self.combFn.create_accumulator(),
                                        [{'attempt_start_usec': None}])
    self.assertEqual(accumulator, [])

  def test_null_timestamp_not_included(self):
    accumulator = self.combFn.add_input(self.combFn.create_accumulator(),
                                        [{'timestamp_millis': None}])
    self.assertEqual(accumulator, [])

  def test_add_input(self):
    row = {
        'attempt_start_usec': self.attempt_start_usec,
        'timestamp_millis': self.timestamp_msec,
        'action': self.combFn.ACTION_PATCH_START,
    }
    event = objects.CQEvent.from_bigquery_row(row)
    accumulator = self.combFn.add_input(self.combFn.create_accumulator(), [row])
    self.assertEqual(accumulator, [event])

  def test_extract_min_timestamp_one_timestamp(self):
    accumulator = [self.basic_event()]
    attempt = self.combFn.extract_output(accumulator)
    self.assertEqual(attempt['first_start_msec'], self.timestamp_msec)

  def test_extract_min_timestamp(self):
    accumulator = [
      self.basic_event(timestamp_millis=self.timestamp_msec),
      self.basic_event(timestamp_millis=self.earlier_timestamp),
      self.basic_event(timestamp_millis=self.later_timestamp),
    ]
    attempt = self.combFn.extract_output(accumulator)
    self.assertEqual(attempt['first_start_msec'], self.earlier_timestamp)

  def test_extract_max_timestamp(self):
    accumulator = [
      self.basic_event(timestamp_millis=self.timestamp_msec),
      self.basic_event(timestamp_millis=self.later_timestamp),
      self.basic_event(timestamp_millis=self.earlier_timestamp),
    ]
    attempt = self.combFn.extract_output(accumulator)
    self.assertEqual(attempt['last_start_msec'], self.later_timestamp)

  def test_extract_attempt_start(self):
    accumulator = [self.basic_event()]
    attempt = self.combFn.extract_output(accumulator)
    self.assertEqual(attempt['attempt_start_msec'], self.attempt_start_msec)

  def test_extract_different_attempt_start(self):
    accumulator = [
        self.basic_event(attempt_start_usec=self.attempt_start_usec),
        self.basic_event(attempt_start_usec=self.attempt_start_usec+1000)
    ]
    with self.assertRaises(AssertionError):
      self.combFn.extract_output(accumulator)

  def test_extract_consistent_field(self):
    event = self.basic_event()
    attempt = self.combFn.extract_output([event])
    self.assertEqual(attempt['cq_name'], event.cq_name)

  def test_extract_different_consistent_field(self):
    accumulator = [
        self.basic_event(),
        self.basic_event(cq_name='different_cq_name')
    ]
    with self.assertRaises(AssertionError):
      self.combFn.extract_output(accumulator)

  def test_extract_logical_or(self):
    accumulator = [self.basic_event(action=self.combFn.ACTION_PATCH_COMMITTED)]
    attempt = self.combFn.extract_output(accumulator)
    self.assertTrue(attempt['committed'])

  def test_filter_incomplete_attempts(self):
    test_cases = [
        {
          'attempt': {
            'first_start_msec': self.timestamp_msec,
            'last_stop_msec': self.timestamp_msec,
          },
          'filtered_expected': False
        },
        {
          'attempt': {
            'first_start_msec': None,
            'last_stop_msec': self.timestamp_msec,
          },
          'filtered_expected': True
        },
        {
          'attempt': {
            'first_start_msec': self.timestamp_msec,
            'last_stop_msec': None,
          },
          'filtered_expected': True
        }
    ]
    for test_case in test_cases:
      attempt = test_case['attempt']
      filter_attempts = job.ComputeAttempts.filter_incomplete_attempts
      if test_case['filtered_expected']:
        with self.assertRaises(StopIteration):
          filtered_attempt = filter_attempts(attempt).next()
      else:
        filtered_attempt = filter_attempts(attempt).next()
        self.assertEqual(filtered_attempt, attempt)


if __name__ == '__main__':
  unittest.main()
