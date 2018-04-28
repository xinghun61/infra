# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import exceptions
from common.waterfall import failure_type
from gae_libs.pipelines import pipeline
from libs import analysis_status
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from pipelines.compile_failure.run_compile_try_job_pipeline import (
    RunCompileTryJobPipeline)
from services import try_job
from services.compile_failure import compile_try_job
from services.parameters import BuildKey
from services.parameters import RunCompileTryJobParameters
from waterfall.test import wf_testcase


class RunCompileTryJobPipelineTest(wf_testcase.WaterfallTestCase):

  def _CreateRunCompileTryJobParameters(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = job.key
    try_job_data.try_job_url = (
        'https://build.chromium.org/p/m/builders/b/builds/1234')
    try_job_data.put()
    job.compile_results = [{
        'report': None,
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'try_job_id': '1',
    }]
    job.status = analysis_status.RUNNING
    job.put()

    return RunCompileTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        good_revision='rev1',
        bad_revision='rev2',
        suspected_revisions=['r5'],
        cache_name=None,
        dimensions=[],
        force_buildbot=False,
        compile_targets=[],
        urlsafe_try_job_key=job.key.urlsafe())

  @mock.patch.object(try_job, 'OnTryJobTimeout')
  def testOnTimeout(self, mocked_OnTryJobTimeout):
    pipeline_input = self._CreateRunCompileTryJobParameters()
    p = RunCompileTryJobPipeline(pipeline_input)
    p.OnTimeout(pipeline_input, {'try_job_id': 'id'})
    mocked_OnTryJobTimeout.assert_called_once_with('id', failure_type.COMPILE)

  @mock.patch.object(
      RunCompileTryJobPipeline, 'GetCallbackParameters', return_value={})
  @mock.patch.object(RunCompileTryJobPipeline, 'pipeline_id')
  @mock.patch.object(RunCompileTryJobPipeline, 'SaveCallbackParameters')
  @mock.patch.object(
      compile_try_job, 'ScheduleCompileTryJob', return_value='job_id')
  def testRunImplSuccessfulRun(self, mocked_ScheduleCompileTryJob,
                               mocked_SaveCallbackParameters,
                               mocked_pipeline_id, _):
    mocked_pipeline_id.__get__ = mock.Mock(return_value='pipeline-id')
    pipeline_input = self._CreateRunCompileTryJobParameters()
    p = RunCompileTryJobPipeline(pipeline_input)
    p.RunImpl(pipeline_input)
    mocked_ScheduleCompileTryJob.assert_called_once_with(
        pipeline_input, 'pipeline-id')
    mocked_SaveCallbackParameters.assert_called_once_with({
        'try_job_id': 'job_id'
    })

  @mock.patch.object(
      RunCompileTryJobPipeline,
      'GetCallbackParameters',
      return_value={
          'try_job_id': 'job_id'
      })
  @mock.patch.object(compile_try_job, 'ScheduleCompileTryJob')
  def testRunImplNotTriggerSameJobTwice(self, mocked_ScheduleCompileTryJob, _):
    pipeline_input = self._CreateRunCompileTryJobParameters()
    p = RunCompileTryJobPipeline(pipeline_input)
    p.RunImpl(pipeline_input)
    self.assertFalse(mocked_ScheduleCompileTryJob.called)

  @mock.patch.object(
      RunCompileTryJobPipeline, 'GetCallbackParameters', return_value={})
  @mock.patch.object(RunCompileTryJobPipeline, 'pipeline_id')
  @mock.patch.object(RunCompileTryJobPipeline, 'SaveCallbackParameters')
  @mock.patch.object(
      compile_try_job, 'ScheduleCompileTryJob', return_value=None)
  def testRunImplRetryUponFailure(self, mocked_ScheduleCompileTryJob,
                                  mocked_SaveCallbackParameters,
                                  mocked_pipeline_id, _):
    mocked_pipeline_id.__get__ = mock.Mock(return_value='pipeline-id')
    pipeline_input = self._CreateRunCompileTryJobParameters()
    p = RunCompileTryJobPipeline(pipeline_input)
    with self.assertRaises(pipeline.Retry):
      p.RunImpl(pipeline_input)
    mocked_ScheduleCompileTryJob.assert_called_once_with(
        pipeline_input, 'pipeline-id')
    self.assertFalse(mocked_SaveCallbackParameters.called)

  @mock.patch.object(compile_try_job, 'OnTryJobStateChanged')
  @mock.patch.object(RunCompileTryJobPipeline, 'pipeline_id')
  def testCallbackImplNoTryJobID(self, mocked_pipeline_id,
                                 mocked_OnTryJobStateChanged):
    mocked_pipeline_id.__get__ = mock.Mock(return_value='pipeline-id')
    pipeline_input = self._CreateRunCompileTryJobParameters()
    p = RunCompileTryJobPipeline(pipeline_input)
    returned_value = p.CallbackImpl(pipeline_input, {'build_json': '{"k":"v"}'})
    self.assertEqual(('Try_job_id not found for pipeline pipeline-id', None),
                     returned_value)
    self.assertFalse(mocked_OnTryJobStateChanged.called)

  @mock.patch.object(
      compile_try_job, 'OnTryJobStateChanged', return_value='dummy')
  def testCallbackImplCompletedRun(self, mocked_OnTryJobStateChanged):
    pipeline_input = self._CreateRunCompileTryJobParameters()
    p = RunCompileTryJobPipeline(pipeline_input)
    returned_value = p.CallbackImpl(pipeline_input, {
        'try_job_id': 'job-id',
        'build_json': '{"k":"v"}'
    })
    self.assertEqual((None, 'dummy'), returned_value)
    mocked_OnTryJobStateChanged.assert_called_once_with('job-id', {'k': 'v'})

  @mock.patch.object(compile_try_job, 'OnTryJobStateChanged', return_value=None)
  def testCallbackImplNotCompletedRun(self, mocked_OnTryJobStateChanged):
    pipeline_input = self._CreateRunCompileTryJobParameters()
    p = RunCompileTryJobPipeline(pipeline_input)
    returned_value = p.CallbackImpl(pipeline_input, {
        'try_job_id': 'job-id',
        'build_json': '{"k":"v"}'
    })
    self.assertIsNone(returned_value)
    mocked_OnTryJobStateChanged.assert_called_once_with('job-id', {'k': 'v'})

  @mock.patch.object(
      compile_try_job,
      'OnTryJobStateChanged',
      side_effect=exceptions.RetryException('r', 'm'))
  def testCallbackImplFailedRun(self, mocked_OnTryJobStateChanged):
    pipeline_input = self._CreateRunCompileTryJobParameters()
    p = RunCompileTryJobPipeline(pipeline_input)
    returned_value = p.CallbackImpl(pipeline_input, {
        'try_job_id': 'job-id',
        'build_json': '{"k":"v"}'
    })
    self.assertEqual(('Error on updating try-job result: m', None),
                     returned_value)
    mocked_OnTryJobStateChanged.assert_called_once_with('job-id', {'k': 'v'})

  def testTimeoutSeconds(self):
    pipeline_input = self._CreateRunCompileTryJobParameters()
    p = RunCompileTryJobPipeline(pipeline_input)
    self.assertEqual(36000, p.TimeoutSeconds())
