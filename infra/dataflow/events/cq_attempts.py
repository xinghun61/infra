# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

import apache_beam as beam

from infra.dataflow.events import aggregate_objects
from infra.dataflow.events import chops_beam

ACTION_PATCH_START = 'PATCH_START'


class CombineEventsToAttempt(beam.CombineFn):
  def create_accumulator(self):
    return aggregate_objects.CQAttempt()

  def add_input(self, accumulator, input_rows):
    for row in input_rows:
      if row.get('attempt_start_usec') is None:
        logging.warn('recieved row with null attempt_start_usec: %s', row)
        continue

      timestamp = row.get('timestamp_millis')
      if timestamp is None:
        logging.warn('recieved raw with null timestamp: %s', row)
        continue

      attempt_start_msec = row.get('attempt_start_usec') / 1000
      assert (accumulator.attempt_start_msec is None or
              accumulator.attempt_start_msec == attempt_start_msec)
      accumulator.attempt_start_msec = attempt_start_msec
      action = row.get('action')

      if action == ACTION_PATCH_START:
        accumulator.update_first_start(timestamp)
        accumulator.update_last_start(timestamp)

    return accumulator

  def merge_accumulators(self, accumulators):
    if len(accumulators) == 0:
      return aggregate_objects.CQAttempt()
    if len(accumulators) == 1:
      return accumulators[0]
    merged = accumulators[0]
    for a in accumulators[1:]:
      merged.update_first_start(a.first_start_msec)
      merged.update_last_start(a.last_start_msec)
    return merged

  def extract_output(self, a):
    return a.as_bigquery_row()


def main():
  q = ('SELECT timestamp_millis, action, attempt_start_usec '
       'FROM `chrome-infra-events.raw_events.cq` '
       'WHERE timestamp_micros(attempt_start_usec) > '
       '  timestamp_sub(current_timestamp, interval 24 hour)')
  p = chops_beam.EventsPipeline()
  _ = (p
   | chops_beam.BQRead(q)
   | beam.Map(lambda e: (e['attempt_start_usec'], e))
   | beam.GroupByKey()
   | beam.CombinePerKey(CombineEventsToAttempt())
   | beam.Map(lambda (k, v): v)
   | chops_beam.BQWrite('cq_attempts'))
  p.run()


if __name__ == '__main__':
  main()
