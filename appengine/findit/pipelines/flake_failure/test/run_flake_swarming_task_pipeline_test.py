# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from common import exceptions
from dto.flake_swarming_task_output import FlakeSwarmingTaskOutput
from gae_libs.pipeline_wrapper import pipeline_handlers
from gae_libs.pipelines import pipeline
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskInput)
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskPipeline)
from services.flake_failure import flake_swarming
from waterfall.test.wf_testcase import WaterfallTestCase


class RunFlakeSwarmingTaskResultPipeline(WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(
      RunFlakeSwarmingTaskPipeline, 'GetCallbackParameters', return_value={})
  @mock.patch.object(RunFlakeSwarmingTaskPipeline, 'pipeline_id')
  @mock.patch.object(RunFlakeSwarmingTaskPipeline, 'SaveCallbackParameters')
  @mock.patch.object(
      flake_swarming, 'TriggerSwarmingTask', return_value='task_id')
  def testRunImplSuccessfulRun(self, mock_trigger, mock_save_params,
                               mocked_pipeline_id, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200

    run_flake_swarming_task_input = RunFlakeSwarmingTaskInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        timeout_seconds=timeout_seconds)

    mocked_pipeline_id.__get__ = mock.Mock(return_value='pipeline-id')
    pipeline_job = RunFlakeSwarmingTaskPipeline(run_flake_swarming_task_input)
    pipeline_job.RunImpl(run_flake_swarming_task_input)
    mock_trigger.assert_called_once_with(analysis.key.urlsafe(), isolate_sha,
                                         iterations, timeout_seconds,
                                         'pipeline-id')
    mock_save_params.assert_called_once_with({'task_id': 'task_id'})

  @mock.patch.object(
      RunFlakeSwarmingTaskPipeline,
      'GetCallbackParameters',
      return_value={
          'task_id': 'task_id'
      })
  @mock.patch.object(
      flake_swarming, 'TriggerSwarmingTask', return_value='task_id')
  def testRunImplNotTriggerSameTaskTwice(self, mock_trigger, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200

    run_flake_swarming_task_input = RunFlakeSwarmingTaskInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        timeout_seconds=timeout_seconds)

    pipeline_job = RunFlakeSwarmingTaskPipeline(run_flake_swarming_task_input)
    pipeline_job.RunImpl(run_flake_swarming_task_input)
    self.assertFalse(mock_trigger.called)

  @mock.patch.object(
      RunFlakeSwarmingTaskPipeline, 'GetCallbackParameters', return_value={})
  @mock.patch.object(flake_swarming, 'TriggerSwarmingTask')
  @mock.patch.object(RunFlakeSwarmingTaskPipeline, 'pipeline_id')
  def testRunImplTriggerTaskFailed(self, mocked_pipeline_id, mock_trigger, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200

    run_flake_swarming_task_input = RunFlakeSwarmingTaskInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        timeout_seconds=timeout_seconds)

    mock_trigger.return_value = None

    mocked_pipeline_id.__get__ = mock.Mock(return_value='pipeline-id')
    pipeline_job = RunFlakeSwarmingTaskPipeline(run_flake_swarming_task_input)
    with self.assertRaises(pipeline.Retry):
      pipeline_job.RunImpl(run_flake_swarming_task_input)

    mock_trigger.assert_called_once_with(analysis.key.urlsafe(), isolate_sha,
                                         iterations, timeout_seconds,
                                         'pipeline-id')

  @mock.patch.object(flake_swarming, 'OnSwarmingTaskStateChanged')
  @mock.patch.object(RunFlakeSwarmingTaskPipeline, 'pipeline_id')
  def testCallbackImplNoTaskID(self, mocked_pipeline_id, mock_fn):
    mocked_pipeline_id.__get__ = mock.Mock(return_value='pipeline-id')
    pipeline_input = RunFlakeSwarmingTaskInput.FromSerializable({})
    p = RunFlakeSwarmingTaskPipeline(pipeline_input)
    result = p.CallbackImpl(pipeline_input, {})
    self.assertEqual(('Task_id not found for pipeline pipeline-id', None),
                     result)
    self.assertFalse(mock_fn.called)

  @mock.patch.object(flake_swarming, 'OnSwarmingTaskStateChanged')
  def testCallbackImplCompleted(self, mocked_output):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200

    run_flake_swarming_task_input = RunFlakeSwarmingTaskInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        timeout_seconds=timeout_seconds)

    flake_swarming_task_output = FlakeSwarmingTaskOutput(
        completed_time=datetime(2018, 4, 1, 0, 1, 0),
        error=None,
        iterations=iterations,
        pass_count=iterations,
        started_time=datetime(2018, 4, 1, 0, 0, 0),
        task_id='task_id')

    mocked_output.return_value = flake_swarming_task_output

    pipeline_job = RunFlakeSwarmingTaskPipeline(run_flake_swarming_task_input)
    result = pipeline_job.CallbackImpl(None, {'task_id': 'task_id'})
    self.assertEqual((None, flake_swarming_task_output), result)

  @mock.patch.object(
      flake_swarming, 'OnSwarmingTaskStateChanged', return_value=None)
  def testCallbackImplRunning(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')

    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200

    run_flake_swarming_task_input = RunFlakeSwarmingTaskInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        timeout_seconds=timeout_seconds)

    pipeline_job = RunFlakeSwarmingTaskPipeline(run_flake_swarming_task_input)
    result = pipeline_job.CallbackImpl(None, {'task_id': 'task_id'})
    self.assertIsNone(result)

  @mock.patch.object(
      flake_swarming,
      'OnSwarmingTaskStateChanged',
      side_effect=exceptions.RetryException('r', 'm'))
  def testCallbackImplFailedRun(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200

    run_flake_swarming_task_input = RunFlakeSwarmingTaskInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        timeout_seconds=timeout_seconds)

    pipeline_job = RunFlakeSwarmingTaskPipeline(run_flake_swarming_task_input)
    result = pipeline_job.CallbackImpl(None, {'task_id': 'task_id'})
    self.assertEqual(('Error getting swarming task result: m', None), result)

  @mock.patch.object(flake_swarming, 'OnSwarmingTaskTimeout')
  def testOnTimeout(self, mock_fn):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200
    task_id = 'task_id'

    run_flake_swarming_task_input = RunFlakeSwarmingTaskInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        timeout_seconds=timeout_seconds)

    pipeline_job = RunFlakeSwarmingTaskPipeline(run_flake_swarming_task_input)
    pipeline_job.OnTimeout(None, {'task_id': task_id})
    mock_fn.assert_called_once_with(task_id)

  def testTimeoutSeconds(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200

    run_flake_swarming_task_input = RunFlakeSwarmingTaskInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        timeout_seconds=timeout_seconds)

    pipeline_job = RunFlakeSwarmingTaskPipeline(run_flake_swarming_task_input)
    self.assertEqual(24 * 60 * 60, pipeline_job.TimeoutSeconds())
