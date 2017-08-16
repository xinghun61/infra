# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

import apache_beam as beam

from dataflow.common import chops_beam
from dataflow.common import objects


class CombineEventsToAttempt(beam.CombineFn):
  ACTION_PATCH_START = 'PATCH_START'
  ACTION_PATCH_COMMITTED = 'PATCH_COMMITTED'
  ACTION_PATCH_COMMITTING = 'ACTION_PATCH_COMMITTING'
  ACTION_PATCH_STOP = 'PATCH_STOP'
  ACTION_PATCH_THROTTLED = 'PATCH_THROTTLED'
  ACTION_PATCH_TREE_CLOSED = 'PATCH_TREE_CLOSED'
  ACTION_VERIFIER_TRIGGER = 'VERIFIER_TRIGGER'
  ACTION_VERIFIER_PASS = 'VERIFIER_PASS'
  ACTION_VERIFIER_NOTRY = 'VERIFIER_NOTRY'
  ACTION_VERIFIER_CUSTOM_TRYBOTS = 'VERIFIER_CUSTOM_TRYBOTS'
  ACTION_PATCH_FAILED = 'PATCH_FAILED'
  # Try job fail types
  FAIL_TYPE_PATCH = 'FAIL_TYPE_PATCH'
  FAIL_TYPE_INFRA = 'FAIL_TYPE_INFRA'
  FAIL_TYPE_COMPILE = 'FAIL_TYPE_COMPILE'
  FAIL_TYPE_TEST = 'FAIL_TYPE_TEST'
  FAIL_TYPE_INVALID = 'FAIL_TYPE_INVALID'

  def __init__(self):
    super(CombineEventsToAttempt, self).__init__()
    self.action_affects_fields = {
        self.ACTION_PATCH_START: set(['first_start_msec', 'last_start_msec']),
        self.ACTION_PATCH_STOP: set(['first_stop_msec', 'last_stop_msec']),
        self.ACTION_PATCH_COMMITTED: set(['patch_committed_msec', 'committed']),
        self.ACTION_PATCH_COMMITTING: set(['patch_started_to_commit_msec']),
        self.ACTION_PATCH_THROTTLED: set(['was_throttled']),
        self.ACTION_PATCH_TREE_CLOSED: set(['waited_for_tree']),
        self.ACTION_VERIFIER_TRIGGER: set(['first_verifier_trigger_msec']),
        self.ACTION_VERIFIER_PASS: set(['patch_verifier_pass_msec']),
        self.ACTION_VERIFIER_NOTRY: set(['no_tryjobs_launched']),
        self.ACTION_VERIFIER_CUSTOM_TRYBOTS: set(['custom_trybots']),
        self.ACTION_PATCH_FAILED: set(['patch_failed_msec', 'failed',
                                       'failure_reason']),
    }
    self.min_timestamp_fields = set([
        'first_start_msec',
        'first_stop_msec',
        'patch_committed_msec',
        'patch_started_to_commit_msec',
        'first_verifier_trigger_msec',
        'patch_verifier_pass_msec',
        'patch_failed_msec'
    ])
    self.max_timestamp_fields = set([
        'last_start_msec',
        'last_stop_msec',
    ])
    self.logical_or_fields = set([
        'committed',
        'was_throttled',
        'waited_for_tree',
        'failed',
    ])
    # Fields that are copied from event to attempt. Values for these fields are
    # the same for all events for a given attempt.
    self.consistent_fields = set([
        'cq_name',
        'issue',
        'patchset',
        'dry_run',
    ])

  @staticmethod
  def choose_min(old, new):
    if new is not None and (old is None or new < old):
      return new
    return old

  def create_accumulator(self):
    return []

  def add_input(self, accumulator, input_rows):
    for row in input_rows:
      event = objects.CQEvent.from_bigquery_row(row)
      if event.attempt_start_usec is None:
        logging.warn('recieved row with null attempt_start_usec: %s', row)
        continue

      if event.timestamp_millis is None:
        logging.warn('recieved raw with null timestamp: %s', row)
        continue

      accumulator.append(event)
    return accumulator

  def merge_accumulators(self, accumulators):
    merged = self.create_accumulator()
    for a in list(accumulators):
      merged += a
    return merged

  def extract_output(self, accumulator):
    attempt = objects.CQAttempt()

    for event in accumulator:
      attempt_start_msec = float(event.attempt_start_usec) / 1000
      if (attempt.attempt_start_msec and
          attempt.attempt_start_msec != attempt_start_msec):
        logging.error(('tried to combine events with different '
                       'attempt_start_msec'))
        return

      attempt.attempt_start_msec = attempt_start_msec

      # Here we search for the last-reported value of some field.
      if (event.failure_reason and (attempt.max_failure_msec is None
           or event.timestamp_millis > attempt.max_failure_msec)):
        attempt.failure_reason = event.failure_reason
        attempt.max_failure_msec = event.timestamp_millis
        attempt.fail_type = attempt.failure_reason['fail_type']
      if (event.contributing_buildbucket_ids and
          (attempt.max_bbucket_ids_msec is None or
           event.timestamp_millis > attempt.max_bbucket_ids_msec)):
        attempt.contributing_bbucket_ids = event.contributing_buildbucket_ids
        attempt.max_bbucket_ids_msec = event.timestamp_millis

      for field in self.consistent_fields:
        attempt_value = attempt.__dict__.get(field)
        event_value = event.__dict__.get(field)
        if attempt_value and attempt_value  != event_value:
          logging.error('tried to combine events with inconsistent %s', field)
          return
        attempt.__dict__[field] = event_value

      affected_fields = self.action_affects_fields.get(event.action, [])
      for field in affected_fields:
        if field in self.min_timestamp_fields:
          attempt.__dict__[field] = self.choose_min(attempt.__dict__.get(field),
                                                    event.timestamp_millis)
        if field in self.max_timestamp_fields:
          attempt.__dict__[field] = max(attempt.__dict__.get(field),
                                        event.timestamp_millis)
        if field in self.logical_or_fields:
          attempt.__dict__[field] = True

    if attempt.first_verifier_trigger_msec:
      attempt.cq_launch_latency_sec = (attempt.first_verifier_trigger_msec -
                                       attempt.attempt_start_msec) / 1000.0
    if attempt.patch_verifier_pass_msec:
      attempt.verifier_pass_latency_sec = (attempt.patch_verifier_pass_msec -
                                           attempt.attempt_start_msec) / 1000.0
      if attempt.patch_started_to_commit_msec:
        attempt.tree_check_and_throttle_latency_sec = (
            attempt.patch_started_to_commit_msec -
            attempt.patch_verifier_pass_msec) / 1000.0

    # TODO: Deprecate. Now that we have contributing buildbucket ids, we can
    # join with completed_builds to get this information.
    if attempt.failure_reason:
      for job in attempt.failure_reason.get('failed_try_jobs', []):
        fail_type = job['fail_type']
        attempt.total_failures += 1
        if fail_type == self.FAIL_TYPE_INFRA:
          attempt.infra_failures += 1
        if fail_type == self.FAIL_TYPE_COMPILE:
          attempt.compile_failures += 1
        if fail_type == self.FAIL_TYPE_TEST:
          attempt.test_failures += 1
        if fail_type == self.FAIL_TYPE_INVALID:
          attempt.invalid_test_results_failures += 1
        if fail_type == self.FAIL_TYPE_PATCH:
          attempt.patch_failures += 1
    return attempt.as_bigquery_row()


class ComputeAttempts(beam.PTransform):
  @staticmethod
  def key(event):
    parts = [event.get('attempt_start_usec'), event.get('cq_name'),
             event.get('issue'), event.get('patchset')]
    return ':'.join([str(part) or '' for part in parts])

  @staticmethod
  def filter_incomplete_attempts(attempt):
    if (attempt is not None and attempt.get('first_start_msec')
        and attempt.get('last_stop_msec')):
      yield attempt

  def expand(self, pcoll):
    return (pcoll
            | beam.Map(lambda e: (self.key(e), e))
            | beam.GroupByKey()
            | beam.CombinePerKey(CombineEventsToAttempt())
            | beam.Map(lambda (k, v): v)
            | beam.FlatMap(self.filter_incomplete_attempts))


def main():
  q = ('SELECT timestamp_millis, action, attempt_start_usec, cq_name, issue,'
       '  patchset, dry_run, failure_reason, contributing_buildbucket_ids '
       'FROM `chrome-infra-events.raw_events.cq`')
  p = chops_beam.EventsPipeline()
  _ = (p
       | chops_beam.BQRead(q)
       | ComputeAttempts()
       | chops_beam.BQWrite('cq_attempts'))
  p.run()


if __name__ == '__main__':
  main()
