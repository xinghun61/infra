# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import os
import sys
import webapp2

sys.path.insert(0, os.path.join(
  os.path.dirname(os.path.dirname(__file__)), 'third_party'))

from aenum import Enum
import apache_beam as beam
from dataflow.common import chops_beam
from google.appengine.api import taskqueue

from common.request_entity import Request, RequestManager


class AcceptedResults(Enum):
  """ Result types that are valid for the pipeline. """
  PASS = 2
  FAIL = 3
  CRASH = 4
  TIMEOUT = 5

class FilterTestResults(beam.DoFn):
  """ Filter data points with test results we don't support """
  def process(self, element):
    results = element['test_result']
    accepted = [r.value for r in AcceptedResults]
    if all(value in accepted for value in results):
      yield element

class GenerateNDBEntities(beam.CombineFn):
  """ Create an ndb entity for each test and store them in request manager """
  def create_accumulator(self):
    return []

  def add_input(self, accumulator, element):
    request = Request(master_name=element['master_name'],
                      builder_name=element['builder_name'],
                      build_number=element['build_number'],
                      step_name=element['step_name'],
                      test_name=element['test_name'],
                      test_results=element['test_result'])
    accumulator.append(request)
    return accumulator

  def merge_accumulators(self, accumulators):
    # Concatenating a list of lists into one list:
    # https://stackoverflow.com/a/716489
    return sum(accumulators, [])

  def extract_output(self, accumulator):
    manager = RequestManager.load()
    for request in accumulator:
      manager.add_request(request)
    manager.save()
    return accumulator

class TriggerPipelineHandler(webapp2.RequestHandler):
  def get(self):  # pragma: no cover
    # Initial query takes only results that have failures in them
    # with the assumption that if PASS or SKIP is the first result,
    # then the entire test passed
    query = """
    SELECT
      master_name,
      builder_name,
      build_number,
      step_name,
      usec_since_epoch,
      t.test_name,
      t.actual as test_result
    FROM
      plx.google.chrome_infra.test_results.last7days,
      UNNEST(tests) AS t
    WHERE
      /* Only allow results results that contain at least one failure,
         where a failure is a FAIL, CRASH, or TIMEOUT, and no more than 1 PASS */
      exists (select a from t.actual a where a in (3, 4, 5)) AND
      (select count(a) from t.actual a where a = 2) <= 1 AND
      /* For now we are limiting to browser_tests but this will be extended
         to include all tests that contain failing results at which point
         this restriction will be removed */
      step_name = "browser_tests"
    """
    pipeline = chops_beam.EventsPipeline()
    _ = (pipeline
         | chops_beam.BQRead(query)
         | beam.ParDo(FilterTestResults())
         | beam.CombineGlobally(GenerateNDBEntities())
    )
    # TODO(kdillon): Once thread leaking problem is fixed, remove this hack
    # as pipeline.run().wait_until_finish() will be sufficient here
    # https://github.com/apache/beam/pull/3751
    result = pipeline.run()
    result.wait_until_finish()
    result._executor._executor.executor_service.await_completion()

    taskqueue.add(url='/internal/rerun-request-handler', params={
        'time_scheduled': datetime.datetime.utcnow(), 'num_taskqueue_runs': 1},)
