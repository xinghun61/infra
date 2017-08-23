# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from mock import patch
import unittest

import apache_beam as beam
from apache_beam.testing import test_pipeline
from apache_beam.testing import util
from dataflow.common import chops_beam
from google.appengine.ext import ndb

from common.request_entity import Request, RequestManager
from dataflow_pipeline import trigger_pipeline_handler
from dataflow_pipeline.trigger_pipeline_handler import AcceptedResults
import main
from testing_utils import testing


UNEXPECTED_TEST_RESULT = -1


class FetchInitialDataTest(testing.AppengineTestCase):
  app_module = main.app

  def setUp(self):
    super(FetchInitialDataTest, self).setUp()
    ndb.get_context().clear_cache()
    self.accepted_test_result = {'master_name':'test_master',
                                 'builder_name':'test_builder',
                                 'build_number':1234, 'step_name':'test_step',
                                 'test_name':'test', 'test_result':[
                                     AcceptedResults.FAIL.value,
                                     AcceptedResults.PASS.value]}
    self.unsupported_test_result = {'master_name':'test_master',
                                    'builder_name':'test_builder',
                                    'build_number':1234,
                                    'step_name':'test_step', 'test_name':'test',
                                    'test_result':[AcceptedResults.FAIL.value,
                                        UNEXPECTED_TEST_RESULT]}

  def tearDown(self):
    super(FetchInitialDataTest, self).tearDown()

  def test_filter_unsupported_test_results(self):
    pipeline = test_pipeline.TestPipeline()
    result = (pipeline
              | beam.Create(
                  [self.accepted_test_result, self.unsupported_test_result])
              | beam.ParDo(trigger_pipeline_handler.FilterTestResults())
    )
    util.assert_that(result, util.equal_to([self.accepted_test_result]))
    pipeline.run().wait_until_finish(duration=2000)

  def assert_accepted_entity_generated_correctly(self, entity, expected):
    self.assertEqual(entity.master_name, expected['master_name'])
    self.assertEqual(entity.builder_name, expected['builder_name'])
    self.assertEqual(entity.build_number, expected['build_number'])
    self.assertEqual(entity.step_name, expected['step_name'])
    self.assertEqual(entity.test_name, expected['test_name'])
    self.assertEqual(entity.test_results, expected['test_result'])

  def test_generate_ndb_entities(self):
    pipeline = test_pipeline.TestPipeline()
    _ = (pipeline
         | beam.Create([self.accepted_test_result])
         | beam.CombineGlobally(trigger_pipeline_handler.GenerateNDBEntities())
    )
    pipeline.run().wait_until_finish(duration=2000)
    manager = RequestManager.load()
    entity = manager.pending[0].get()
    self.assertEqual(len(manager.pending), 1)
    self.assert_accepted_entity_generated_correctly(
        entity, self.accepted_test_result)

  @patch.object(chops_beam, 'BQRead')
  def test_entire_pipeline(self, mock_bq_read):
    mock_bq_read.return_value = beam.Create([self.accepted_test_result,
                                             self.accepted_test_result,
                                             self.unsupported_test_result])
    response = self.test_app.get('/cron/trigger-pipeline')
    self.assertEqual(response.status_int, 200)

    manager = RequestManager.load()
    entities = ndb.get_multi(manager.pending)
    self.assertEqual(len(manager.pending), 2)
    self.assert_accepted_entity_generated_correctly(
        entities[0], self.accepted_test_result)
    self.assert_accepted_entity_generated_correctly(
        entities[1], self.accepted_test_result)
