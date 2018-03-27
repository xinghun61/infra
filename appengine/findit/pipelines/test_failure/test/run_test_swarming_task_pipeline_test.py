# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import exceptions
from dto.run_swarming_task_parameters import RunSwarmingTaskParameters
from gae_libs.pipelines import pipeline
from pipelines.test_failure.run_test_swarming_task_pipeline import (
    RunTestSwarmingTaskPipeline)
from services.parameters import BuildKey
from services.test_failure import test_swarming
from waterfall.test import wf_testcase


class RunTestSwarmingTaskPipelineTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(RunTestSwarmingTaskPipelineTest, self).setUp()
    self.pipeline_input = RunSwarmingTaskParameters(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=21),
        step_name='s',
        tests=['test'])

  @mock.patch.object(
      RunTestSwarmingTaskPipeline, 'GetCallbackParameters', return_value={})
  @mock.patch.object(RunTestSwarmingTaskPipeline, 'pipeline_id')
  @mock.patch.object(RunTestSwarmingTaskPipeline, 'SaveCallbackParameters')
  @mock.patch.object(
      test_swarming, 'TriggerSwarmingTask', return_value='task_id')
  def testRunImplSuccessfulRun(self, mock_trigger, mock_save_params,
                               mocked_pipeline_id, _):
    mocked_pipeline_id.__get__ = mock.Mock(return_value='pipeline-id')
    p = RunTestSwarmingTaskPipeline(self.pipeline_input)
    p.RunImpl(self.pipeline_input)
    mock_trigger.assert_called_once_with(self.pipeline_input, 'pipeline-id')
    mock_save_params.assert_called_once_with({'task_id': 'task_id'})

  @mock.patch.object(
      RunTestSwarmingTaskPipeline,
      'GetCallbackParameters',
      return_value={
          'task_id': 'task_id'
      })
  @mock.patch.object(
      test_swarming, 'TriggerSwarmingTask', return_value='task_id')
  def testRunImplNotTriggerSameTaskTwice(self, mock_trigger, _):
    p = RunTestSwarmingTaskPipeline(self.pipeline_input)
    p.RunImpl(self.pipeline_input)
    self.assertFalse(mock_trigger.called)

  @mock.patch.object(
      RunTestSwarmingTaskPipeline, 'GetCallbackParameters', return_value={})
  @mock.patch.object(test_swarming, 'TriggerSwarmingTask', return_value=None)
  @mock.patch.object(RunTestSwarmingTaskPipeline, 'pipeline_id')
  def testRunImplTriggerTaskFailed(self, mocked_pipeline_id, *_):
    mocked_pipeline_id.__get__ = mock.Mock(return_value='pipeline-id')
    p = RunTestSwarmingTaskPipeline(self.pipeline_input)
    with self.assertRaises(pipeline.Retry):
      p.RunImpl(self.pipeline_input)

  @mock.patch.object(
      test_swarming, 'OnSwarmingTaskStateChanged', return_value=True)
  def testCallbackImplCompleted(self, _):
    p = RunTestSwarmingTaskPipeline(self.pipeline_input)
    result = p.CallbackImpl(self.pipeline_input, {'task_id': 'task_id'})
    self.assertEqual((None, True), result)

  @mock.patch.object(
      test_swarming, 'OnSwarmingTaskStateChanged', return_value=None)
  def testCallbackImplRunning(self, _):
    p = RunTestSwarmingTaskPipeline(self.pipeline_input)
    result = p.CallbackImpl(self.pipeline_input, {'task_id': 'task_id'})
    self.assertIsNone(result)

  @mock.patch.object(
      test_swarming,
      'OnSwarmingTaskStateChanged',
      side_effect=exceptions.RetryException('r', 'm'))
  def testCallbackImplFailedRun(self, _):
    p = RunTestSwarmingTaskPipeline(self.pipeline_input)
    result = p.CallbackImpl(self.pipeline_input, {'task_id': 'task_id'})
    self.assertEqual(('Error on updating swarming task result: m', None),
                     result)

  @mock.patch.object(test_swarming, 'OnSwarmingTaskTimeout')
  def testOnTimeout(self, mock_fn):
    p = RunTestSwarmingTaskPipeline(self.pipeline_input)
    p.OnTimeout(self.pipeline_input, {'task_id': 'task_id'})
    mock_fn.assert_called_once_with(self.pipeline_input, 'task_id')

  def testTimeoutSeconds(self):
    p = RunTestSwarmingTaskPipeline(self.pipeline_input)
    self.assertEqual(7200, p.TimeoutSeconds())
