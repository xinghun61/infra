# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mock

from common import exceptions
from dto.collect_swarming_task_results_inputs import (
    CollectSwarmingTaskResultsInputs)
from dto.collect_swarming_task_results_outputs import (
    CollectSwarmingTaskResultsOutputs)
from pipelines.test_failure import collect_swarming_task_results_pipeline
from pipelines.test_failure.collect_swarming_task_results_pipeline import (
    CollectSwarmingTaskResultsPipeline)
from services.parameters import BuildKey
from services.test_failure import test_swarming
from waterfall.test import wf_testcase


class CollectSwarmingTaskResultsPipelineTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(CollectSwarmingTaskResultsPipelineTest, self).setUp()
    self.pipeline_input = CollectSwarmingTaskResultsInputs(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=41),
        build_completed=True)

  def testGetCountDown(self):
    self.assertEqual(300,
                     collect_swarming_task_results_pipeline._GetCountDown(1))
    self.assertEqual(60,
                     collect_swarming_task_results_pipeline._GetCountDown(8))

  def testTimeoutSeconds(self):
    p = CollectSwarmingTaskResultsPipeline(
        CollectSwarmingTaskResultsInputs.FromSerializable({}))
    self.assertEqual(82800, p.TimeoutSeconds())

  @mock.patch.object(
      CollectSwarmingTaskResultsPipeline,
      'GetCallbackParameters',
      return_value={
          'steps': ['step']
      })
  @mock.patch.object(test_swarming, 'GetStepsToCollectSwarmingTaskResults')
  def testRunImplNotCalledTwice(self, mock_fn, _):
    p = CollectSwarmingTaskResultsPipeline(self.pipeline_input)
    p.RunImpl(self.pipeline_input)
    self.assertFalse(mock_fn.called)

  @mock.patch.object(
      CollectSwarmingTaskResultsPipeline,
      'GetCallbackParameters',
      return_value={})
  @mock.patch.object(CollectSwarmingTaskResultsPipeline, 'ScheduleCallbackTask')
  @mock.patch.object(CollectSwarmingTaskResultsPipeline,
                     'SaveCallbackParameters')
  @mock.patch.object(
      test_swarming,
      'GetStepsToCollectSwarmingTaskResults',
      return_value=['step'])
  def testRunImplSucceeds(self, mock_fn, mock_save, mocked_schedule, _):
    p = CollectSwarmingTaskResultsPipeline(self.pipeline_input)
    p.RunImpl(self.pipeline_input)
    mock_fn.assert_called_once_with(self.pipeline_input)
    mock_save.assert_called_once_with({'steps': ['step'], 'callback_count': 0})
    mocked_schedule.assert_called_once_with(countdown=0)

  @mock.patch.object(CollectSwarmingTaskResultsPipeline, 'ScheduleCallbackTask')
  @mock.patch.object(test_swarming, 'GetConsistentFailuresWhenAllTasksComplete')
  def testCallbackImplCompleted(self, mock_fn, mock_schedule):
    consitent_failures = CollectSwarmingTaskResultsOutputs.FromSerializable({
        'consistent_failures': {
            'step': ['test']
        }
    })
    mock_fn.return_value = consitent_failures

    p = CollectSwarmingTaskResultsPipeline(self.pipeline_input)
    result = p.CallbackImpl(self.pipeline_input, {
        'steps': ['step'],
        'callback_count': 0
    })
    self.assertEqual((None, consitent_failures), result)
    mock_fn.assert_called_once_with(self.pipeline_input, ['step'])
    self.assertFalse(mock_schedule.called)

  @mock.patch.object(CollectSwarmingTaskResultsPipeline,
                     'SaveCallbackParameters')
  @mock.patch.object(CollectSwarmingTaskResultsPipeline, 'ScheduleCallbackTask')
  @mock.patch.object(
      test_swarming,
      'GetConsistentFailuresWhenAllTasksComplete',
      return_value=None)
  def testCallbackImplRunning(self, mock_fn, mock_schedule, mock_save):
    p = CollectSwarmingTaskResultsPipeline(self.pipeline_input)
    result = p.CallbackImpl(self.pipeline_input, {
        'steps': ['step'],
        'callback_count': 3
    })
    self.assertIsNone(result)
    mock_fn.assert_called_once_with(self.pipeline_input, ['step'])
    mock_schedule.assert_called_once_with(countdown=120)
    mock_save.assert_called_once_with({'steps': ['step'], 'callback_count': 4})

  @mock.patch.object(CollectSwarmingTaskResultsPipeline, 'ScheduleCallbackTask')
  @mock.patch.object(
      test_swarming,
      'GetConsistentFailuresWhenAllTasksComplete',
      side_effect=exceptions.RetryException('r', 'm'))
  def testCallbackImplFailedRun(self, mock_fn, mock_schedule):
    p = CollectSwarmingTaskResultsPipeline(self.pipeline_input)
    result = p.CallbackImpl(self.pipeline_input, {
        'steps': ['step'],
        'callback_count': 3
    })
    self.assertEqual(('Error on updating swarming task result: m', None),
                     result)
    mock_fn.assert_called_once_with(self.pipeline_input, ['step'])
    self.assertFalse(mock_schedule.called)

  @mock.patch.object(logging, 'error')
  def testOnTimeOut(self, mock_fn):
    p = CollectSwarmingTaskResultsPipeline(self.pipeline_input)
    p.OnTimeout(self.pipeline_input, {'steps': ['step'], 'callback_count': 3})
    mock_fn.assert_called_once_with(
        'Timed out when collecting results of swarming tasks.')
