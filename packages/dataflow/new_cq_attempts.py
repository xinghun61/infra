# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import apache_beam as beam

from dataflow import cq_attempts as sanitize_cq_attempts
from dataflow.common import chops_beam


class ExtractBuildBucketIdFn(beam.DoFn):
  def process(self, cq_attempt_with_key):
    # For a CQ attempt, we create one row for each contributing BuildBucket id.
    key = cq_attempt_with_key[0]
    cq_attempt_dict = cq_attempt_with_key[1]

    bb_ids = cq_attempt_dict.get('contributing_bbucket_ids')
    if bb_ids:
      for bb_id in bb_ids:
        yield str(bb_id), key

class FilterJoinedBuildBucketCQAttempt(beam.DoFn):
  def process(self, joined_result):
    # The key is BuildBucket ID. We expect there to be exactly 1 cq_attempt, and
    # up to 1 BuildBucket entry.
    cq_attempt_key = joined_result[1]['cq_attempt_key']
    bb_entry = joined_result[1]['bb_entries']
    if len(bb_entry) != 1 or len(cq_attempt_key) != 1:
      return
    yield cq_attempt_key[0], bb_entry[0]

def update_with_presubmit_failure(input_tuple):
  value = input_tuple[1]
  cq_attempts = value['cq_attempts']
  assert len(cq_attempts) == 1, "There must be 1 cq_attempt."
  cq_attempt = cq_attempts[0]

  if cq_attempt['fail_type'] == 'FAILED_JOBS':
    buildbucket_results = value['bb_entries']
    presubmit_failures = 0
    other_failures = 0
    for bb_result in buildbucket_results:
      if (bb_result['status'] == 'FAILURE' and
          bb_result['builder'] == 'chromium_presubmit'):
        presubmit_failures += 1
      elif bb_result['status'] != 'SUCCESS':
        other_failures += 1
    if presubmit_failures >= 1 and other_failures == 0:
      cq_attempt['fail_type'] = 'FAILED_PRESUBMIT_BOT'

  # Dictionaries are supposed to be returned in a single element list.
  return [cq_attempt]

def process_input(cq_events_pcol, bb_entries_pcol):
  """Sets up the pipeline stages to return aggregated cq attempts pcol.

  This function performs two tasks:
    1) Computes CQ attempts from raw CQ events. This includes data sanitization.
    2) If a CQ attempt fails only because of 'chromium_presubmit' builder, sets
       the failure status to 'FAILED_PRESUBMIT_BOT'.
  """
  # Pcol of cq_attempt_as_dict
  sanitized_cq_attempts = (
      cq_events_pcol | sanitize_cq_attempts.ComputeAttempts())

  # Create Pcol of tuples: (cq_attempt_key, cq_attempt_as_dict)
  def extract_key(cq_attempt_dict):
    key_parts = [
      cq_attempt_dict.get('attempt_start_msec'),
      cq_attempt_dict.get('cq_name'),
      cq_attempt_dict.get('issue'),
      cq_attempt_dict.get('patchset')
    ]
    key = ':'.join([str(part) or '' for part in key_parts])
    return key, cq_attempt_dict
  cq_attempts_with_key = sanitized_cq_attempts | beam.Map(extract_key)

  # Create Pcol of tuples: (build_bucket_id, cq_attempt_key)
  cq_attempt_key_keyed_by_bb_id = cq_attempts_with_key | beam.ParDo(
      ExtractBuildBucketIdFn())

  # Create Pcol of tuples: (build_bucket_id, build_bucket_entry)
  bb_entry_keyed_by_bb_id = bb_entries_pcol | beam.Map(
      lambda e: (str(e.get('id')), e))

  # Create Pcol of tuples: (cq_attempt_key, BuildBucket entry)
  bb_entries_keyed_by_cq_attempt_key = ({
    'bb_entries' : bb_entry_keyed_by_bb_id,
    'cq_attempt_key': cq_attempt_key_keyed_by_bb_id
  } | 'Join BuildBucket with cq attempts' >> beam.CoGroupByKey()
    | beam.ParDo(FilterJoinedBuildBucketCQAttempt())
  )

  # Uses BuildBucket entries associated with a CQ attempt to potentially change
  # the failure reason to FAILED_PRESUBMIT_BOT. Creates a Pcol of
  # cq_attempt_as_dict.
  results = ({
    'cq_attempts' : cq_attempts_with_key,
    'bb_entries' : bb_entries_keyed_by_cq_attempt_key
  } | beam.CoGroupByKey()
    | beam.FlatMap(update_with_presubmit_failure)
  )
  return results

def main():
  p = chops_beam.EventsPipeline()
  q = ('SELECT timestamp_millis, action, attempt_start_usec, cq_name, issue,'
       '  patchset, dry_run, failure_reason, contributing_buildbucket_ids, '
       '  earliest_equivalent_patchset '
       'FROM `chrome-infra-events.raw_events.cq`')
  cq_events_pcol = p | 'read raw CQ events' >> chops_beam.BQRead(q)

  q = ('SELECT id, builder.builder, status from '
       '`cr-buildbucket.chromium.builds`')
  bb_entries_pcol = p | 'read BuildBucket' >> chops_beam.BQRead(q)

  results = process_input(cq_events_pcol, bb_entries_pcol)

  # pylint: disable=expression-not-assigned
  results | chops_beam.BQWrite('chrome-infra-events', 'cq_attempts')

  p.run()


if __name__ == '__main__':
  main()
