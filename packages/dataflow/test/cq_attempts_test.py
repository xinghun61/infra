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

  @staticmethod
  def construct_attempt_values(attempt_start_usec, actions,
                               failure_reasons=None):
    cq_name = 'test_cq'
    issue = '1'
    patchset = '1'

    event_basic = {
      'attempt_start_usec': attempt_start_usec,
      'cq_name': cq_name,
      'issue': issue,
      'patchset': patchset,
    }

    events = []
    for i, action in enumerate(actions):
      event = event_basic.copy()
      event.update({
        'action': action[0],
        'timestamp_millis': action[1],
        'failure_reason': failure_reasons[i] if failure_reasons else None,
      })
      events.append(event)

    attempt = objects.CQAttempt()
    attempt.cq_name = cq_name
    attempt.attempt_start_msec = float(attempt_start_usec) / 1000
    attempt.issue = issue
    attempt.patchset = patchset

    return (events, attempt)


  def failed_attempt_values(self, attempt_start_usec):
    actions = [
      (self.combFn.ACTION_PATCH_START, 1000),
      (self.combFn.ACTION_VERIFIER_CUSTOM_TRYBOTS, 2000),
      (self.combFn.ACTION_PATCH_FAILED, 5000),
      (self.combFn.ACTION_PATCH_FAILED, 6000),
      (self.combFn.ACTION_PATCH_STOP, 9000),
    ]

    failure_reasons = [
      None,
      None,
      {
        'fail_type': 'FAIL_TYPE_1',
        'failed_try_jobs': [
          {'fail_type': self.combFn.FAIL_TYPE_TEST},
          {'fail_type': self.combFn.FAIL_TYPE_TEST},
          {'fail_type': self.combFn.FAIL_TYPE_TEST},
          {'fail_type': self.combFn.FAIL_TYPE_PATCH},
        ]
      },
      {
        'fail_type': 'FAIL_TYPE_2',
        'failed_try_jobs': [
          {'fail_type': self.combFn.FAIL_TYPE_COMPILE},
          {'fail_type': self.combFn.FAIL_TYPE_INVALID},
        ]
      },
      None,
    ]

    events, attempt = self.construct_attempt_values(attempt_start_usec, actions,
                                                    failure_reasons)

    attempt.first_start_msec = 1000
    attempt.last_start_msec = 1000
    attempt.last_stop_msec = 9000
    attempt.first_stop_msec = 9000
    attempt.fail_type = 'FAIL_TYPE_2'
    attempt.failed = True
    attempt.patch_failed_msec = 5000
    attempt.invalid_test_results_failures = 1
    attempt.compile_failures = 1
    attempt.total_failures = 2
    attempt.custom_trybots = True
    attempt.click_to_failure_sec = 4.0
    attempt.click_to_result_sec = 8.0

    return (events, attempt.as_bigquery_row())


  def complete_attempt_values(self, attempt_start_usec):
    actions = [
      (self.combFn.ACTION_PATCH_START, 1000),
      (self.combFn.ACTION_VERIFIER_TRIGGER, 3000),
      (self.combFn.ACTION_VERIFIER_PASS, 4000),
      (self.combFn.ACTION_PATCH_COMMITTING, 5000),
      (self.combFn.ACTION_PATCH_COMMITTED, 6000),
      (self.combFn.ACTION_PATCH_STOP, 9000),
    ]

    events, attempt = self.construct_attempt_values(attempt_start_usec, actions)

    events[-2]['contributing_buildbucket_ids'] = [1]
    events[-1]['contributing_buildbucket_ids'] = [2, 3]

    attempt.first_start_msec = 1000
    attempt.last_start_msec = 1000
    attempt.last_stop_msec = 9000
    attempt.first_stop_msec = 9000
    attempt.cq_launch_latency_sec = 3.0
    attempt.verifier_pass_latency_sec = 4.0
    attempt.tree_check_and_throttle_latency_sec = 1.0
    attempt.vcs_commit_latency_sec = 1.0
    attempt.click_to_patch_committed_sec = 6.0
    attempt.click_to_result_sec = 9.0
    attempt.committed = True
    attempt.contributing_bbucket_ids = [2, 3]

    return (events, attempt.as_bigquery_row())

  def test_compute_attempts(self):
    complete_attempt_events, complete_attempt = self.complete_attempt_values(
        attempt_start_usec=0)
    failed_attempt_events, failed_attempt = self.failed_attempt_values(
        attempt_start_usec=1000000) # 1 second

    incomplete_attempt_events = [
        {
            'timestamp_millis': 2,
            'action': self.combFn.ACTION_PATCH_START,
            'attempt_start_usec': 1,
            'cq_name': 'test_cq',
            'issue': '2',
            'patchset': '1',
        },
    ]

    events = (complete_attempt_events + failed_attempt_events +
              incomplete_attempt_events)
    expected_attempts = [complete_attempt, failed_attempt]

    p = test_pipeline.TestPipeline()
    pcoll = (p
             | beam.Create(events)
             | job.ComputeAttempts())
    util.assert_that(pcoll, util.equal_to(expected_attempts))
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
    event.issue = '123'
    event.patchset = '456'
    event.dry_run = True
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
    self.assertIsNone(self.combFn.extract_output(accumulator))

  def test_extract_consistent_field(self):
    event = self.basic_event()
    attempt = self.combFn.extract_output([event])
    for field in self.combFn.consistent_fields:
      self.assertEqual(attempt[field], event.__dict__[field])

  def test_extract_different_consistent_field(self):
    accumulator = [
        self.basic_event(),
        self.basic_event(cq_name='different_cq_name')
    ]
    self.assertIsNone(self.combFn.extract_output(accumulator))

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
