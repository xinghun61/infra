# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import infra.dataflow.events.cq_attempts as job

from infra.dataflow.events import aggregate_objects


class TestCQAttemptAccumulator(unittest.TestCase):
  def setUp(self):
    self.attempt_start_usec = 1493833887566000
    self.attempt_start_msec = self.attempt_start_usec / 1000
    self.patch_start = 1493833887688
    self.combFn = job.CombineEventsToAttempt()
    self.basic_accumulator = self.new_basic_accumulator()

  def new_basic_accumulator(self):
    basic_accumulator = aggregate_objects.CQAttempt()
    basic_accumulator.attempt_start_msec = self.attempt_start_msec
    basic_accumulator.first_start_msec = self.patch_start
    basic_accumulator.last_start_msec = self.patch_start
    return basic_accumulator

  def test_add_first_start(self):
    accumulator = aggregate_objects.CQAttempt()
    rows = [{
        'attempt_start_usec': self.attempt_start_usec,
        'timestamp_millis': self.patch_start,
        'action': job.ACTION_PATCH_START,
    }]
    accumulator = self.combFn.add_input(accumulator, rows)
    self.assertEqual(accumulator.first_start_msec, self.patch_start)
    self.assertEqual(accumulator.last_start_msec, self.patch_start)

  def test_add_null_start(self):
    rows = [{
        'attempt_start_usec': self.attempt_start_usec,
        'timestamp_millis': None,
        'action': job.ACTION_PATCH_START,
    }]
    self.combFn.add_input(self.basic_accumulator, rows)
    self.assertEqual(self.basic_accumulator.first_start_msec, self.patch_start)
    self.assertEqual(self.basic_accumulator.last_start_msec, self.patch_start)

  def test_add_earlier_start(self):
    earlier_patch_start = self.patch_start - 1
    rows = [{
        'attempt_start_usec': self.attempt_start_usec,
        'timestamp_millis': earlier_patch_start,
        'action': job.ACTION_PATCH_START,
    }]
    self.combFn.add_input(self.basic_accumulator, rows)
    self.assertEqual(self.basic_accumulator.first_start_msec,
                     earlier_patch_start)
    self.assertEqual(self.basic_accumulator.last_start_msec, self.patch_start)

  def test_add_later_start(self):
    later_patch_start = self.patch_start + 1
    rows = [{
        'attempt_start_usec': self.attempt_start_usec,
        'timestamp_millis': later_patch_start,
        'action': job.ACTION_PATCH_START,
    }]
    self.combFn.add_input(self.basic_accumulator, rows)
    self.assertEqual(self.basic_accumulator.first_start_msec, self.patch_start)
    self.assertEqual(self.basic_accumulator.last_start_msec, later_patch_start)

  def test_merge_null_start(self):
    another = aggregate_objects.CQAttempt()
    merged = self.combFn.merge_accumulators([self.basic_accumulator, another])
    self.assertEqual(merged.first_start_msec, self.patch_start)
    self.assertEqual(merged.last_start_msec, self.patch_start)

  def test_merge_earlier_start(self):
    another = self.new_basic_accumulator()
    earlier_patch_start = self.patch_start - 1
    another.first_start_msec = earlier_patch_start
    merged = self.combFn.merge_accumulators([self.basic_accumulator, another])
    self.assertEqual(merged.first_start_msec, earlier_patch_start)
    self.assertEqual(merged.last_start_msec, self.patch_start)

  def test_merge_later_start(self):
    another = self.new_basic_accumulator()
    later_patch_start = self.patch_start + 1
    another.last_start_msec = later_patch_start
    merged = self.combFn.merge_accumulators([self.basic_accumulator, another])
    self.assertEqual(merged.first_start_msec, self.patch_start)
    self.assertEqual(merged.last_start_msec, later_patch_start)

if __name__ == '__main__':
  unittest.main()
