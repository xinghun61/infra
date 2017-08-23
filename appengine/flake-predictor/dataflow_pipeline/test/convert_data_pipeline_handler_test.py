# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
from mock import patch
import unittest

import apache_beam as beam
from apache_beam.testing import test_pipeline
from apache_beam.testing import util
from dataflow.common import chops_beam
from google.appengine.ext import ndb

from common.request_entity import Request, RequestManager, Status
from common import snippets
from dataflow_pipeline import convert_data_pipeline_handler
from dataflow_pipeline.convert_data_pipeline_handler import (
    COLUMN_ORDER, FLAKY, NOT_FLAKY)
import cloudstorage
import main
from testing_utils import testing
from time_functions.testing import mock_datetime_utc


FLAKY_SWARMING_RESPONSE = {
  'completed': True,
  'total_reruns': '100',
  'fail_count': '50',
}
NON_FLAKY_SWARMING_RESPONSE = {
  'completed': True,
  'total_reruns': '100',
  'fail_count': '0',
}
FAULTY_SWARMING_RESPONSE = {
  'completed': True,
  'total_reruns': 'one-hundred',
  'fail_count': 'zero',
}
CSV = ','.join(COLUMN_ORDER) + '\n' + (
    """1,master,builder,1234,step,test,[],['output', 'snippet']\n""")


class MockWriter(beam.io.iobase.Writer):
  """Mock for beam.io.WriteToText. Original class: https://goo.gl/umw9rE"""
  def __init__(self, results):
    self.results = results

  def write(self, elem):
    self.results.append(elem)

  def close(self):
    pass

class MockTextSink(beam.io.iobase.Sink):
  """Mock for beam.io.WriteToText. Original class: https://goo.gl/ofsFE6"""
  results = []

  def __init__(self, *args, **kwargs):
    pass

  def initialize_write(self):
    pass

  def open_writer(self, _init_data, _bundle_id):
    return MockWriter(self.results)

  def finalize_write(self, *args, **kwargs):
    pass

class ConvertDataPipelineTest(testing.AppengineTestCase):
  app_module = main.app

  def setUp(self):
    super(ConvertDataPipelineTest, self).setUp()
    # Clear cache between tests to reset manager
    ndb.get_context().clear_cache()

  def tearDown(self):
    super(ConvertDataPipelineTest, self).tearDown()

  def test_extract_elements_into_pairs(self):
    manager = RequestManager.load()
    manager.add_request(Request(master_name='test_master',
                                builder_name='test_builder',
                                build_number=1234, step_name='test_step',
                                test_name='test', test_results=[],
                                status=Status.COMPLETED,
                                swarming_response=None))
    manager.save()
    pairs = convert_data_pipeline_handler.extract_elements_into_pairs()
    self.assertEquals(len(pairs), 1)
    self.assertEquals(pairs[0][0]['master_name'], 'test_master')
    self.assertEquals(pairs[0][0]['builder_name'], 'test_builder')
    self.assertEquals(pairs[0][0]['build_number'], 1234)
    self.assertEquals(pairs[0][0]['step_name'], 'test_step')
    self.assertEquals(pairs[0][1]['test_name'], 'test')
    self.assertEquals(pairs[0][1]['test_results'], [])
    self.assertEquals(pairs[0][1]['swarming_response'], None)
    self.assertEquals(manager.key.get(), None)

  @patch.object(snippets, 'get_processed_output_snippet_batch')
  def test_get_output_snippets(self, mock_snippets):
    mock_snippets.return_value = {'test':['output', 'snippet']}
    grouped_pairs = ({'master_name': 'test_master',
                      'builder_name':'test_builder', 'build_number':1234,
                      'step_name':'test_step'},
                     [{'test_name':'test', 'test_results':[],
                       'swarming_response':None}, {'test_name':'no_snippet'}])
    pipeline = test_pipeline.TestPipeline()
    result = (pipeline
              | beam.Create([grouped_pairs])
              | beam.ParDo(convert_data_pipeline_handler.GetOutputSnippet())
    )
    util.assert_that(result, util.equal_to([{'master_name': 'test_master',
                                             'builder_name':'test_builder',
                                             'build_number':1234,
                                             'step_name':'test_step',
                                             'test_name':'test',
                                             'test_results':[],
                                             'swarming_response':None,
                                             'output_snippet':[
                                                 'output', 'snippet']}]))
    # TODO(kdillon): Once thread leaking problem is fixed, remove this hack
    # as pipeline.run() will be sufficient here
    # https://github.com/apache/beam/pull/3751
    result = pipeline.run()
    result._executor._executor.executor_service.await_completion()

  def test_generate_labels(self):
    flaky_test_result = {'swarming_response': FLAKY_SWARMING_RESPONSE}
    non_flaky_test_result = {'swarming_response': NON_FLAKY_SWARMING_RESPONSE}
    faulty_test_result = {'swarming_response': FAULTY_SWARMING_RESPONSE}
    pipeline = test_pipeline.TestPipeline()
    result = (pipeline
              | beam.Create([flaky_test_result, non_flaky_test_result,
                             faulty_test_result])
              | beam.ParDo(convert_data_pipeline_handler.GenerateLabels())
    )
    util.assert_that(result, util.equal_to([
        {'swarming_response': FLAKY_SWARMING_RESPONSE, 'label': FLAKY},
        {'swarming_response': NON_FLAKY_SWARMING_RESPONSE, 'label':NOT_FLAKY}]))
    # TODO(kdillon): Once thread leaking problem is fixed, remove this hack
    # as pipeline.run() will be sufficient here
    # https://github.com/apache/beam/pull/3751
    result = pipeline.run()
    result._executor._executor.executor_service.await_completion()

  @mock_datetime_utc(2017, 8, 8, 1, 0, 0)
  @patch.object(snippets, 'get_processed_output_snippet_batch')
  @patch.object(beam.io.textio, '_TextSink', MockTextSink)
  def test_entire_pipeline(self, mock_snippets):
    mock_snippets.return_value = {'test':['output', 'snippet']}
    manager = RequestManager.load()
    manager.add_request(Request(master_name='master',
                                builder_name='builder',
                                build_number=1234, step_name='step',
                                test_name='test', test_results=[],
                                status=Status.COMPLETED,
                                swarming_response=FLAKY_SWARMING_RESPONSE))
    manager.save()
    self.test_app.get('/internal/convert-data-pipeline-handler')
    self.assertEqual([CSV], MockTextSink.results)
