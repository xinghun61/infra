# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import unittest

import apache_beam as beam
from apache_beam.testing import test_pipeline
from apache_beam.testing import util

from dataflow import cq_attempts as sanitize_cq_attempts
from dataflow import new_cq_attempts


def _beam_equals(expected, actual):
  if expected != actual:
    raise util.BeamAssertException(
        'Expected {} to equal {}'.format(expected, actual))


class IntegrationTest(unittest.TestCase):
  def setUp(self):
    self.pipeline = test_pipeline.TestPipeline()

  def construct_cq_events_pcol(self, failure_reason=None):
    attempt_start_usec = 1000000
    cq_name = 'test_cq'
    issue = '1'
    patchset = '1'
    combine_class = sanitize_cq_attempts.CombineEventsToAttempt
    actions = [
      combine_class.ACTION_PATCH_START,
      combine_class.ACTION_VERIFIER_CUSTOM_TRYBOTS,
      combine_class.ACTION_PATCH_FAILED,
      combine_class.ACTION_PATCH_FAILED,
      combine_class.ACTION_PATCH_STOP,
    ]

    event_basic = {
      'attempt_start_usec': attempt_start_usec,
      'cq_name': cq_name,
      'issue': issue,
      'patchset': patchset,
    }

    events = []
    for i, action in enumerate(actions):
      event = event_basic.copy()
      event_failure_reason = (failure_reason if
          action == combine_class.ACTION_PATCH_FAILED else None)
      event.update({
        'action': action,
        'timestamp_millis': 1000 * (i + 1),
        'failure_reason': event_failure_reason,
      })
      if action == combine_class.ACTION_VERIFIER_CUSTOM_TRYBOTS:
        event['contributing_buildbucket_ids'] = [11, 12]
      events.append(event)

    return self.pipeline | beam.Create(events)

  def construct_bb_entries_pcol(self, builder_name, status):
    bb_entries = [{'id':11, 'builder': builder_name, 'status':status}]
    return self.pipeline | 'Construct BuildBucket entries' >> beam.Create(
        bb_entries)

  # One CQ attempt, with matching BuildBucket entries that all pass.
  def test_basic_pass(self):
    cq_events_pcol = self.construct_cq_events_pcol()
    bb_entries_pcol = self.construct_bb_entries_pcol('random_builder',
                                                     'SUCCESS')
    results = new_cq_attempts.process_input(cq_events_pcol, bb_entries_pcol)

    # There should be exactly 1 CQ attempt, with no fail type.
    def expectation_checker(cq_attempts):
      _beam_equals(len(cq_attempts), 1)
      _beam_equals(cq_attempts[0]['fail_type'], None)

    util.assert_that(results, expectation_checker)
    self.pipeline.run()

  def test_basic_failure_random_builder(self):
    failure_reason = {'fail_type': 'FAILED_JOBS'}
    cq_events_pcol = self.construct_cq_events_pcol(failure_reason)
    bb_entries_pcol = self.construct_bb_entries_pcol('random_builder',
                                                     'FAILURE')
    results = new_cq_attempts.process_input(cq_events_pcol, bb_entries_pcol)

    # There should be exactly 1 CQ attempt, with no fail type.
    def expectation_checker(cq_attempts):
      _beam_equals(len(cq_attempts), 1)
      _beam_equals(cq_attempts[0]['fail_type'], 'FAILED_JOBS')

    util.assert_that(results, expectation_checker)
    self.pipeline.run()

  def test_basic_failure_chromium_presubmit(self):
    failure_reason = {'fail_type': 'FAILED_JOBS'}
    cq_events_pcol = self.construct_cq_events_pcol(failure_reason)
    bb_entries_pcol = self.construct_bb_entries_pcol(
        'chromium_presubmit', 'FAILURE')
    results = new_cq_attempts.process_input(cq_events_pcol, bb_entries_pcol)

    # There should be exactly 1 CQ attempt, with no fail type.
    def expectation_checker(cq_attempts):
      _beam_equals(len(cq_attempts), 1)
      _beam_equals(cq_attempts[0]['fail_type'], 'FAILED_PRESUBMIT_BOT')

    util.assert_that(results, expectation_checker)
    self.pipeline.run()

  def test_two_failures(self):
    failure_reason = {'fail_type': 'FAILED_JOBS'}
    cq_events_pcol = self.construct_cq_events_pcol(failure_reason)
    bb_entries = [
        {'id':11, 'builder': 'chromium_presubmit', 'status':'FAILURE'},
        {'id':12, 'builder': 'win7-rel', 'status':'INFRA_FAILURE'},
    ]
    bb_entries_pcol = (self.pipeline | 'Construct BuildBucket entries' >>
        beam.Create(bb_entries))
    results = new_cq_attempts.process_input(cq_events_pcol, bb_entries_pcol)

    # There should be exactly 1 CQ attempt, with no fail type.
    def expectation_checker(cq_attempts):
      _beam_equals(len(cq_attempts), 1)
      _beam_equals(cq_attempts[0]['fail_type'], 'FAILED_JOBS')

    util.assert_that(results, expectation_checker)
    self.pipeline.run()

  def test_cq_attempt_no_bb_entries(self):
    cq_events_pcol = self.construct_cq_events_pcol()
    bb_entries_pcol = (
        self.pipeline | 'Construct 0 BuildBucket entries' >> beam.Create([]))

    results = new_cq_attempts.process_input(cq_events_pcol, bb_entries_pcol)

    # There should be exactly 1 CQ attempt, with no fail type.
    def expectation_checker(cq_attempts):
      _beam_equals(len(cq_attempts), 1)
      cq_attempt = cq_attempts[0]
      _beam_equals(cq_attempt['fail_type'], None)
      _beam_equals(cq_attempt['issue'], '1')

    util.assert_that(results, expectation_checker)
    self.pipeline.run()


if __name__ == '__main__':
  unittest.main()
