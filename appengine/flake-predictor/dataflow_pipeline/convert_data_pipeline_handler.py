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

import apache_beam as beam
from dataflow.common import chops_beam
from dataflow.common import combine_fns
from google.appengine.api import taskqueue

from common import snippets
from common.request_entity import Request, RequestManager


FLAKINESS_THRESHOLD_MIN = 0.01
FLAKINESS_THRESHOLD_MAX = 0.99
BUCKET = 'gs://flake-predictor-data/training_data/'
COLUMN_ORDER = ['label', 'master_name', 'builder_name', 'build_number',
                'step_name', 'test_name', 'test_results', 'output_snippet']
FLAKY = 1
NOT_FLAKY = 0


def extract_elements_into_pairs():
  """Get data for each test from ndb and put them in key-value pairs"""
  elements = []
  manager = RequestManager.load()
  for ndb_key in manager.completed:
    entity = ndb_key.get()
    key = {'master_name': entity.master_name,
           'builder_name': entity.builder_name,
           'build_number': entity.build_number,
           'step_name': entity.step_name}
    value = {'test_name': entity.test_name,
             'test_results': entity.test_results,
             'swarming_response': entity.swarming_response}
    elements.append((key, value))
  manager.delete()
  return elements

class GetOutputSnippet(beam.DoFn):
  """Get the output snippet for each test"""
  def process(self, element):
    key = element[0]
    values = element[1]
    test_names = [value['test_name'] for value in values]

    output_snippets = snippets.get_processed_output_snippet_batch(
        key['master_name'], key['builder_name'], key['build_number'],
        key['step_name'], test_names)

    for value in values:
      if value['test_name'] in output_snippets:
        element = {'master_name': key['master_name'],
                   'builder_name': key['builder_name'],
                   'build_number': key['build_number'],
                   'step_name': key['step_name'],
                   'test_name': value['test_name'],
                   'test_results': value['test_results'],
                   'swarming_response': value['swarming_response'],
                   'output_snippet': output_snippets[value['test_name']]}
        yield element

class GenerateLabels(beam.DoFn):
  """Generate labels from number of passes and fails in swarming rerun

  An element is labeled flaky if there was at least 1 failure and 1 pass in the
  reruns. If the number of passes and fails cannot be extracted from the
  element, the element is discarded.
  """
  def process(self, element):
    num_rerun_fails = element['swarming_response']['fail_count']
    num_reruns = element['swarming_response']['total_reruns']
    try:
      flakiness = float(num_rerun_fails) / float(num_reruns)
      is_flaky = (flakiness >= FLAKINESS_THRESHOLD_MIN and
                  flakiness <= FLAKINESS_THRESHOLD_MAX)
      label = FLAKY if is_flaky else NOT_FLAKY
      element['label'] = label
      yield element
    except ValueError:
      logging.exception(
          'Could not convert swarming response fields to floats')

class ConvertDataPipelineHandler(webapp2.RequestHandler):
  def get(self):
    file_name = (
        'training-data-' +  datetime.datetime.utcnow().strftime('%Y-%m-%d')
        + '.csv')
    elements = extract_elements_into_pairs()
    pipeline = chops_beam.EventsPipeline()
    _ = (pipeline
         | beam.Create(elements)
         | beam.GroupByKey()
         | beam.ParDo(GetOutputSnippet())
         | beam.ParDo(GenerateLabels())
         | beam.CombineGlobally(combine_fns.ConvertToCSV(COLUMN_ORDER))
         | beam.io.WriteToText(BUCKET + file_name)
    )
    # TODO(kdillon): Once thread leaking problem is fixed, remove this hack
    # as pipeline.run().wait_until_finish() will be sufficient here
    # https://github.com/apache/beam/pull/3751
    result = pipeline.run()
    result.wait_until_finish()
    result._executor._executor.executor_service.await_completion()
    taskqueue.add(url='/internal/cleanup-gcs-handler')
