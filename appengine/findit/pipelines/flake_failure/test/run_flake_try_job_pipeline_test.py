# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import exceptions
from common.waterfall import failure_type
from gae_libs.pipelines import pipeline
from libs import analysis_status
from libs.list_of_basestring import ListOfBasestring
from model.flake.analysis.flake_try_job import FlakeTryJob
from model.flake.analysis.flake_try_job_data import FlakeTryJobData
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure.run_flake_try_job_pipeline import (
    RunFlakeTryJobParameters)
from pipelines.flake_failure.run_flake_try_job_pipeline import (
    RunFlakeTryJobPipeline)
from services import try_job as try_job_service
from services.flake_failure import flake_try_job
from waterfall.test import wf_testcase


class RunFlakeTryJobPipelineTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(try_job_service, 'OnTryJobTimeout')
  def testOnTimeout(self, mocked_OnTryJobTimeout):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()
    revision = 'r1000'
    try_job_url = 'url'
    try_job_id = 'try_job_id'
    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.try_job_url = try_job_url
    try_job_data.put()
    try_job.flake_results = [{
        'report': None,
        'url': try_job_url,
        'try_job_id': try_job_id,
    }]
    try_job.status = analysis_status.RUNNING
    try_job.put()

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        revision=revision,
        isolate_target_name='target',
        urlsafe_try_job_key=try_job.key.urlsafe())
    p = RunFlakeTryJobPipeline(pipeline_input)
    p.OnTimeout(pipeline_input, {'try_job_id': try_job_id})

    mocked_OnTryJobTimeout.assert_called_once_with(try_job_id,
                                                   failure_type.FLAKY_TEST)

  @mock.patch.object(
      RunFlakeTryJobPipeline, 'GetCallbackParameters', return_value={})
  @mock.patch.object(RunFlakeTryJobPipeline, 'pipeline_id')
  @mock.patch.object(RunFlakeTryJobPipeline, 'SaveCallbackParameters')
  @mock.patch.object(flake_try_job, 'ScheduleFlakeTryJob')
  def testGetTryJobsForFlakeSuccess(self, mocked_schedule, mocked_save,
                                    mocked_pipeline_id, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'
    revision = 'r1000'
    isolate_target_name = 'target'
    try_job_id = 'try_job_id'

    mocked_pipeline_id.__get__ = mock.Mock(return_value='pipeline-id')
    mocked_schedule.return_value = try_job_id

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.put()

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        revision=revision,
        isolate_target_name=isolate_target_name,
        urlsafe_try_job_key=try_job.key.urlsafe())

    try_job_pipeline = RunFlakeTryJobPipeline(pipeline_input)
    try_job_pipeline.RunImpl(pipeline_input)

    mocked_schedule.assert_called_once_with(pipeline_input, 'pipeline-id')
    mocked_save.assert_called_once_with({'try_job_id': try_job_id})

  @mock.patch.object(
      RunFlakeTryJobPipeline,
      'GetCallbackParameters',
      return_value={'try_job_id': 'try_job_id'})
  @mock.patch.object(flake_try_job, 'ScheduleFlakeTryJob')
  def testRunImplTriggerSameJobTwice(self, mocked_schedule, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'
    revision = 'r1000'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.put()

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        revision=revision,
        isolate_target_name='target',
        urlsafe_try_job_key=try_job.key.urlsafe())

    try_job_pipeline = RunFlakeTryJobPipeline(pipeline_input)
    try_job_pipeline.RunImpl(pipeline_input)

    self.assertFalse(mocked_schedule.called)

  @mock.patch.object(
      RunFlakeTryJobPipeline, 'GetCallbackParameters', return_value={})
  @mock.patch.object(RunFlakeTryJobPipeline, 'pipeline_id')
  @mock.patch.object(RunFlakeTryJobPipeline, 'SaveCallbackParameters')
  @mock.patch.object(flake_try_job, 'ScheduleFlakeTryJob', return_value=None)
  def testRunImplRetryUponFailure(self, mocked_schedule, mocked_save,
                                  mocked_pipeline_id, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'
    isolate_target_name = 'target'
    revision = 'r1000'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.put()

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        revision=revision,
        isolate_target_name=isolate_target_name,
        urlsafe_try_job_key=try_job.key.urlsafe())

    mocked_pipeline_id.__get__ = mock.Mock(return_value='pipeline-id')
    pipeline_job = RunFlakeTryJobPipeline(pipeline_input)

    with self.assertRaises(pipeline.Retry):
      pipeline_job.RunImpl(pipeline_input)

    mocked_schedule.assert_called_once_with(pipeline_input, 'pipeline-id')
    self.assertFalse(mocked_save.called)

  @mock.patch.object(flake_try_job, 'OnTryJobStateChanged')
  @mock.patch.object(RunFlakeTryJobPipeline, 'pipeline_id')
  def testCallbackImplNoTryJobID(self, mocked_pipeline_id,
                                 mocked_state_changed):
    mocked_pipeline_id.__get__ = mock.Mock(return_value='pipeline-id')

    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'
    isolate_target_name = 'target'
    revision = 'r1000'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.put()

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        revision=revision,
        isolate_target_name=isolate_target_name,
        urlsafe_try_job_key=try_job.key.urlsafe())

    pipeline_job = RunFlakeTryJobPipeline(pipeline_input)
    returned_value = pipeline_job.CallbackImpl(pipeline_input,
                                               {'build_json': '{"k":"v"}'})
    self.assertEqual(('Try_job_id not found for pipeline pipeline-id', None),
                     returned_value)
    self.assertFalse(mocked_state_changed.called)

  @mock.patch.object(
      flake_try_job, 'OnTryJobStateChanged', return_value='dummy')
  def testCallbackImplCompletedRun(self, mocked_state_changed):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'
    isolate_target_name = 'target'
    revision = 'r1000'
    try_job_id = 'try_job_id'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.put()

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        revision=revision,
        isolate_target_name=isolate_target_name,
        urlsafe_try_job_key=try_job.key.urlsafe())

    pipeline_job = RunFlakeTryJobPipeline(pipeline_input)
    returned_value = pipeline_job.CallbackImpl(pipeline_input, {
        'try_job_id': try_job_id,
        'build_json': '{"k":"v"}'
    })
    self.assertEqual((None, 'dummy'), returned_value)
    mocked_state_changed.assert_called_once_with(try_job_id, {'k': 'v'})

  @mock.patch.object(flake_try_job, 'OnTryJobStateChanged', return_value=None)
  def testCallbackImplNotCompletedRun(self, mocked_state_changed):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'
    revision = 'r1000'
    isolate_target_name = 'target'
    try_job_id = 'try_job_id'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.put()

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        revision=revision,
        isolate_target_name=isolate_target_name,
        urlsafe_try_job_key=try_job.key.urlsafe())

    pipeline_job = RunFlakeTryJobPipeline(pipeline_input)
    returned_value = pipeline_job.CallbackImpl(pipeline_input, {
        'try_job_id': try_job_id,
        'build_json': '{"k":"v"}'
    })
    self.assertIsNone(returned_value)
    mocked_state_changed.assert_called_once_with(try_job_id, {'k': 'v'})

  @mock.patch.object(
      flake_try_job,
      'OnTryJobStateChanged',
      side_effect=exceptions.RetryException('r', 'm'))
  def testCallbackImplFailedRun(self, mocked_state_changed):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'
    revision = 'r1000'
    isolate_target_name = 'target'
    try_job_id = 'try_job_id'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.put()

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        revision=revision,
        isolate_target_name=isolate_target_name,
        urlsafe_try_job_key=try_job.key.urlsafe())

    pipeline_job = RunFlakeTryJobPipeline(pipeline_input)
    returned_value = pipeline_job.CallbackImpl(pipeline_input, {
        'try_job_id': try_job_id,
        'build_json': '{"k":"v"}'
    })
    self.assertEqual(('Error updating try job result: m', None), returned_value)
    mocked_state_changed.assert_called_once_with(try_job_id, {'k': 'v'})
