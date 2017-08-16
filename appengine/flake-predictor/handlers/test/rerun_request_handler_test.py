# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock
import unittest

from google.appengine.ext import ndb
from google.appengine.api import taskqueue

from common.request_entity import Request, RequestManager, Status
from handlers import rerun_request_handler
from findit_api import findit_api
import main
from dataflow_pipeline.trigger_pipeline_handler import AcceptedResults
from testing_utils import testing
from time_functions.testing import mock_datetime_utc


COMPLETED_SWARMING_RESPONSE = {
  'task_id': 12345,
  'completed': True,
  'triggering_source': 'Findit API',
  'total_reruns': '100',
  'fail_count': '50',
  'pass_count': '50',
}
ERROR_SWARMING_RESPONSE = {
  'task_id': 12345,
  'completed': False,
  'error': True,
}
QUEUED_SWARMING_RESPONSE = {'queued': True}
NOT_QUEUED_SWARMING_RESPONSE = {'queued': False}
UNSUPPORTED_SWARMING_RESPONSE = {'unsupported': True}


class RerunRequestHandlerTest(testing.AppengineTestCase):
  app_module = main.app

  def setUp(self):
    super(RerunRequestHandlerTest, self).setUp()
    # Clear cache between tests to reset RequestManager and requests
    ndb.get_context().clear_cache()
    self.mock_findit = mock.Mock(spec=findit_api.FindItAPI)
    mock.patch('findit_api.findit_api.FindItAPI',
               lambda *a, **kw: self.mock_findit).start()
    rerun_request_handler.SWARMING_TASK_LIMIT = 2
    rerun_request_handler.MAX_TIMES_SCHEDULED = 3

  def tearDown(self):
    mock.patch.stopall()
    super(RerunRequestHandlerTest, self).tearDown()

  def create_request_entity(
      self, master_name='test_master', builder_name='test_builder',
      build_number=1234, step_name='test_step', test_name='test',
      test_results=None, status=Status.PENDING,
      swarming_response=None):
    return Request(master_name=master_name, builder_name=builder_name,
                   build_number=build_number, step_name=step_name,
                   test_name=test_name,
                   test_results=test_results or [AcceptedResults.FAIL.value],
                   status=status, swarming_response=swarming_response)

  def assert_same_entity(self, entity, expected):
    self.assertEqual(entity.master_name, expected.master_name)
    self.assertEqual(entity.builder_name, expected.builder_name)
    self.assertEqual(entity.build_number, expected.build_number)
    self.assertEqual(entity.step_name, expected.step_name)
    self.assertEqual(entity.test_name, expected.test_name)
    self.assertEqual(entity.test_results, expected.test_results)
    self.assertEqual(entity.status, expected.status)
    self.assertEqual(entity.swarming_response, expected.swarming_response)

  def test_update_pending_queue(self):
    self.mock_findit.checkFlakeSwarmingTask.side_effect = [
        COMPLETED_SWARMING_RESPONSE, NOT_QUEUED_SWARMING_RESPONSE]
    manager = RequestManager.load()
    manager.add_request(self.create_request_entity())
    manager.add_request(self.create_request_entity())
    rerun_request_handler._update_pending_queue(manager, self.mock_findit)
    self.assertEqual(len(manager.pending), 1)
    self.assertEqual(len(manager.completed), 1)
    self.assert_same_entity(manager.completed[0].get(),
                            self.create_request_entity(
                                status=Status.COMPLETED,
                                swarming_response=COMPLETED_SWARMING_RESPONSE))
    self.assert_same_entity(manager.pending[0].get(),
                            self.create_request_entity())

  def test_schedule_test_reruns_until_task_limit(self):
    self.mock_findit.triggerFlakeSwarmingTask.side_effect = [
        UNSUPPORTED_SWARMING_RESPONSE, QUEUED_SWARMING_RESPONSE,
        QUEUED_SWARMING_RESPONSE]
    manager = RequestManager.load()
    manager.add_request(self.create_request_entity())
    manager.add_request(self.create_request_entity())
    manager.add_request(self.create_request_entity())
    manager.add_request(self.create_request_entity())
    rerun_request_handler._schedule_test_reruns(manager, self.mock_findit)
    self.assertEqual(len(manager.pending), 1)
    self.assertEqual(len(manager.running), 2)
    running = self.create_request_entity(status=Status.RUNNING)
    self.assert_same_entity(manager.running[0].get(), running)
    self.assert_same_entity(manager.running[1].get(), running)
    self.assert_same_entity(manager.pending[0].get(),
                            self.create_request_entity())

  def test_schedule_test_reruns_until_no_more_pending(self):
    self.mock_findit.triggerFlakeSwarmingTask.side_effect = [
        QUEUED_SWARMING_RESPONSE]
    manager = RequestManager.load()
    manager.add_request(self.create_request_entity())
    rerun_request_handler._schedule_test_reruns(manager, self.mock_findit)
    self.assertEqual(len(manager.pending), 0)
    self.assertEqual(len(manager.running), 1)
    self.assert_same_entity(manager.running[0].get(),
                            self.create_request_entity(status=Status.RUNNING))

  def test_update_running_queue(self):
    self.mock_findit.checkFlakeSwarmingTask.side_effect = [
        QUEUED_SWARMING_RESPONSE, COMPLETED_SWARMING_RESPONSE,
        ERROR_SWARMING_RESPONSE]
    manager = RequestManager.load()
    manager.add_request(self.create_request_entity(status=Status.RUNNING))
    manager.add_request(self.create_request_entity(status=Status.RUNNING))
    manager.add_request(self.create_request_entity(status=Status.RUNNING))
    rerun_request_handler._update_running_queue(manager, self.mock_findit)
    self.assertEqual(len(manager.running), 1)
    self.assertEqual(len(manager.completed), 1)
    self.assert_same_entity(manager.running[0].get(),
                            self.create_request_entity(status=Status.RUNNING))
    self.assert_same_entity(manager.completed[0].get(),
                            self.create_request_entity(
                                status=Status.COMPLETED,
                                swarming_response=COMPLETED_SWARMING_RESPONSE))

  def test_integration(self):
    manager = RequestManager.load()
    for _ in range(6):
      manager.add_request(self.create_request_entity())
    manager.save()

    @mock_datetime_utc(2017, 8, 8, 1, 0, 0)
    def test_initial_trigger():
      """Set up the manager and trigger the first run of the handler"""
      self.mock_findit.checkFlakeSwarmingTask.return_value = (
          NOT_QUEUED_SWARMING_RESPONSE)
      self.mock_findit.triggerFlakeSwarmingTask.return_value = (
          QUEUED_SWARMING_RESPONSE)
      self.test_app.get('/handlers/rerun-request-handler')
      manager = RequestManager.load()
      tasks = self.taskqueue_stub.get_filtered_tasks()
      params = tasks[0].extract_params()
      self.assertEqual(len(tasks), 1)
      self.assertEqual(params['time_scheduled'], '2017-08-08 01:00:00')
      self.assertEqual(int(params['num_taskqueue_runs']), 2)
      taskqueue.Queue().purge()
      self.assertEqual(len(manager.pending), 4)
      self.assertEqual(len(manager.running), 2)
      self.assertEqual(len(manager.completed), 0)


    @mock_datetime_utc(2017, 8, 9, 1, 0, 0)
    def test_subsequent_trigger():
      """Schedule new reruns since a day has passed and update running"""
      self.mock_findit.triggerFlakeSwarmingTask.return_value = (
          QUEUED_SWARMING_RESPONSE)
      self.mock_findit.checkFlakeSwarmingTask.return_value = (
          COMPLETED_SWARMING_RESPONSE)
      self.test_app.get('/handlers/rerun-request-handler',
                        {'time_scheduled': datetime.datetime.utcnow() -
                         datetime.timedelta(hours=24),
                         'num_taskqueue_runs': 2})
      manager = RequestManager.load()
      tasks = self.taskqueue_stub.get_filtered_tasks()
      params = tasks[0].extract_params()
      self.assertEqual(len(tasks), 1)
      self.assertEqual(params['time_scheduled'], '2017-08-09 01:00:00')
      self.assertEqual(int(params['num_taskqueue_runs']), 3)
      taskqueue.Queue().purge()
      self.assertEqual(len(manager.pending), 2)
      self.assertEqual(len(manager.running), 2)
      self.assertEqual(len(manager.completed), 2)

    @mock_datetime_utc(2017, 8, 10, 1, 0, 0)
    def test_final_trigger():
      """Updates running and shedules no new tasks: limit has been reached"""
      self.mock_findit.checkFlakeSwarmingTask.side_effect = [
          COMPLETED_SWARMING_RESPONSE, QUEUED_SWARMING_RESPONSE]
      self.test_app.get('/handlers/rerun-request-handler',
                        {'time_scheduled': datetime.datetime.utcnow() -
                         datetime.timedelta(hours=24),
                         'num_taskqueue_runs': 3})
      manager = RequestManager.load()
      tasks = self.taskqueue_stub.get_filtered_tasks()
      self.assertEqual(len(tasks), 0)
      taskqueue.Queue().purge()
      self.assertEqual(len(manager.pending), 2)
      self.assertEqual(len(manager.running), 1)
      self.assertEqual(len(manager.completed), 3)

    test_initial_trigger()
    test_subsequent_trigger()
    test_final_trigger()
