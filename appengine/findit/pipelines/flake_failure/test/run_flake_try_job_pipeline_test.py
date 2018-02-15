# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import mock
import time

from google.appengine.api import taskqueue

from common import exceptions
from common.waterfall import buildbucket_client
from dto.list_of_basestring import ListOfBasestring
from gae_libs.pipelines import pipeline
from libs import analysis_status
from model.flake.flake_try_job import FlakeTryJob
from model.flake.flake_try_job_data import FlakeTryJobData
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure.run_flake_try_job_pipeline import (
    RunFlakeTryJobParameters)
from pipelines.flake_failure.run_flake_try_job_pipeline import (
    RunFlakeTryJobPipeline)
from services import try_job as try_job_service
from services.flake_failure import flake_try_job
from waterfall import build_util
from waterfall.test import wf_testcase


class RunFlakeTryJobPipelineTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(flake_try_job, 'ScheduleFlakeTryJob')
  @mock.patch.object(try_job_service, 'OnTryJobCompleted')
  @mock.patch.object(build_util, 'GetWaterfallBuildStepLog')
  @mock.patch.object(buildbucket_client, 'GetTryJobs')
  def testGetTryJobsForFlakeSuccessSerializedCallback(
      self, mock_buildbucket, mock_report, mock_result, mock_schedule):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'
    revision = 'r1000'
    try_job_id = 'try_job_id'
    isolate_sha = 'sha1'
    try_job_url = 'https://build.chromium.org/p/m/builders/b/builds/1234'

    mock_schedule.return_value = try_job_id

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

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

    build_response = {
        'id': try_job_id,
        'url': try_job_url,
        'status': 'COMPLETED',
        'completed_ts': '1454367574000000',
        'created_ts': '1454367570000000',
        'updated_ts': '1454367574000000',
    }
    report = {'isolated_tests': {step_name: [isolate_sha]}}
    mock_buildbucket.return_value = [
        (None, buildbucket_client.BuildbucketBuild(build_response))
    ]
    mock_report.return_value = report
    expected_flake_result = {
        'report': {
            'isolated_tests': {
                step_name: [isolate_sha]
            },
            'metadata': {},
            'previously_checked_out_revision': 'r9999',
            'previously_cached_revision': 'r9999',
            'result': {},
        },
        'url': try_job_url,
        'try_job_id': try_job_id,
    }
    mock_result.return_value = expected_flake_result

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        revision=revision,
        urlsafe_try_job_key=try_job.key.urlsafe())

    try_job_pipeline = RunFlakeTryJobPipeline(pipeline_input)
    try_job_pipeline.start_test()
    try_job_pipeline.run(pipeline_input)
    try_job_pipeline.callback(
        callback_params=json.dumps(try_job_pipeline.last_params))

    # Reload from ID to get all internal properties in sync.
    try_job_pipeline = RunFlakeTryJobPipeline.from_id(
        try_job_pipeline.pipeline_id)
    try_job_pipeline.finalized()
    flake_result = try_job_pipeline.outputs.default.value
    self.assertEqual(expected_flake_result, flake_result)

  @mock.patch.object(taskqueue, 'Queue')
  @mock.patch.object(
      try_job_service, 'GetCurrentTryJobID', return_value='try_job_id')
  @mock.patch.object(try_job_service, '_UpdateTryJobEntity')
  @mock.patch.object(
      flake_try_job, 'ScheduleFlakeTryJob', return_value='try_job_id')
  @mock.patch.object(try_job_service, 'OnTryJobCompleted')
  @mock.patch.object(build_util, 'GetWaterfallBuildStepLog')
  @mock.patch.object(buildbucket_client, 'GetTryJobs')
  def testGetTryJobsForCompileMissingTryJobData(self, mock_buildbucket,
                                                mock_report, mock_result, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'
    revision = 'r1000'
    try_job_id = 'try_job_id'
    try_job_url = 'https://build.chromium.org/p/m/builders/b/builds/1234'
    isolate_sha = 'sha1'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.put()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.compile_results = [{
        'report': None,
        'url': try_job_url,
        'try_job_id': try_job_id,
    }]
    try_job.status = analysis_status.RUNNING
    try_job.put()
    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.try_job_url = try_job_url
    try_job_data.put()

    data = [{
        'build': {
            'id': try_job_id,
            'url': try_job_url,
            'status': 'STARTED'
        }
    }, {
        'error': {
            'reason': 'BUILD_NOT_FOUND',
            'message': 'message',
        }
    }, {
        'build': {
            'id': try_job_id,
            'url': try_job_url,
            'status': 'STARTED'
        }
    }, {
        'error': {
            'reason': 'BUILD_NOT_FOUND',
            'message': 'message',
        }
    }, {
        'build': {
            'id': try_job_id,
            'url': try_job_url,
            'status': 'COMPLETED',
        }
    }]

    report = {
        'isolated_tests': {
            step_name: [isolate_sha]
        },
        'metadata': {},
        'previously_checked_out_revision': 'r9999',
        'previously_cached_revision': 'r9999',
        'result': {},
    }

    get_tryjobs_responses = [
        [(None, buildbucket_client.BuildbucketBuild(data[0]['build']))],
        [(buildbucket_client.BuildbucketError(data[1]['error']), None)],
        [(None, buildbucket_client.BuildbucketBuild(data[2]['build']))],
        [(buildbucket_client.BuildbucketError(data[3]['error']), None)],
        [(None, buildbucket_client.BuildbucketBuild(data[4]['build']))],
    ]
    mock_buildbucket.side_effect = get_tryjobs_responses
    mock_report.return_value = report
    expected_flake_result = {
        'report': report,
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'try_job_id': try_job_id,
    }
    mock_result.return_value = expected_flake_result

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        revision=revision,
        urlsafe_try_job_key=try_job.key.urlsafe())
    try_job_pipeline = RunFlakeTryJobPipeline(pipeline_input)
    try_job_pipeline.start_test()
    try_job_pipeline.run(pipeline_input)
    # Since run() calls callback() immediately, we use -1.
    for _ in range(len(get_tryjobs_responses) - 1):
      try_job_pipeline.callback(callback_params=try_job_pipeline.last_params)

    # Reload from ID to get all internal properties in sync.
    try_job_pipeline = RunFlakeTryJobPipeline.from_id(
        try_job_pipeline.pipeline_id)
    try_job_pipeline.finalized()
    flake_result = try_job_pipeline.outputs.default.value

    self.assertEqual(expected_flake_result, flake_result)

  @mock.patch.object(flake_try_job, 'ScheduleFlakeTryJob', return_value=None)
  def testReturnEmptyDictIfNoTryJobId(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'
    revision = 'r1000'
    try_job_id = 'try_job_id'
    try_job_url = 'try_job_url'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.compile_results = [{
        'report': None,
        'url': try_job_url,
        'try_job_id': try_job_id,
    }]
    try_job.status = analysis_status.RUNNING
    try_job.put()
    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.try_job_url = try_job_url
    try_job_data.put()

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        revision=revision,
        urlsafe_try_job_key=try_job.key.urlsafe())

    try_job_pipeline = RunFlakeTryJobPipeline(pipeline_input)
    try_job_pipeline.start_test()
    try_job_pipeline.run(pipeline_input)

    # Reload from ID to get all internal properties in sync.
    try_job_pipeline = RunFlakeTryJobPipeline.from_id(
        try_job_pipeline.pipeline_id)
    try_job_pipeline.finalized()
    flake_result = try_job_pipeline.outputs.default.value
    self.assertEqual({}, flake_result)

  @mock.patch.object(logging, 'warning')
  @mock.patch.object(
      RunFlakeTryJobPipeline,
      'get_callback_task',
      side_effect=taskqueue.TombstonedTaskError)
  def testDelayCallbackException(self, _, mocked_logging):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'
    revision = 'r1000'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        revision=revision,
        urlsafe_try_job_key=None)

    try_job_pipeline = RunFlakeTryJobPipeline(pipeline_input)
    try_job_pipeline.start_test()
    try_job_pipeline.DelayCallback(
        60, try_job_pipeline.last_params, name='name')
    self.assertTrue(mocked_logging.called)

  @mock.patch.object(flake_try_job, 'ScheduleFlakeTryJob')
  @mock.patch.object(try_job_service, 'OnGetTryJobError')
  @mock.patch.object(buildbucket_client, 'GetTryJobs')
  def testMonitorTryJobMaxError(self, mock_buildbucket, mock_get_error,
                                mock_schedule):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'
    revision = 'r1000'
    try_job_id = 'try_job_id'

    mock_schedule.return_value = try_job_id
    mock_get_error.side_effect = exceptions.RetryException(
        'error_reason', 'error_message')

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.put()

    error_data = {'reason': 'BUILD_NOT_FOUND', 'message': 'message'}
    error = buildbucket_client.BuildbucketError(error_data)
    mock_buildbucket.return_value = [(error, None)]

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        revision=revision,
        urlsafe_try_job_key=try_job.key.urlsafe())

    try_job_pipeline = RunFlakeTryJobPipeline(pipeline_input)
    try_job_pipeline.start_test()
    with self.assertRaises(pipeline.Retry):
      try_job_pipeline.run(pipeline_input)

  @mock.patch.object(
      flake_try_job,
      'ScheduleFlakeTryJob',
      side_effect=exceptions.RetryException('error_reason', 'error_message'))
  def testScheduleNewTryJobForFlake(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
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
        urlsafe_try_job_key=try_job.key.urlsafe())

    try_job_pipeline = RunFlakeTryJobPipeline(pipeline_input)
    with self.assertRaises(pipeline.Retry):
      try_job_pipeline.run(pipeline_input)

  @mock.patch.object(try_job_service, 'UpdateTryJobMetadata')
  @mock.patch.object(flake_try_job, 'ScheduleFlakeTryJob')
  @mock.patch.object(try_job_service, 'OnTryJobRunning')
  @mock.patch.object(build_util, 'GetWaterfallBuildStepLog')
  @mock.patch.object(buildbucket_client, 'GetTryJobs')
  def testCallbackTryJobRunning(self, mock_buildbucket, mock_report,
                                mock_running, mock_schedule, mock_update):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'
    revision = 'r1000'
    try_job_id = 'try_job_id'
    isolate_sha = 'sha1'
    try_job_url = 'https://build.chromium.org/p/m/builders/b/builds/1234'

    mock_schedule.return_value = try_job_id

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

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

    build_response = {
        'id': try_job_id,
        'url': try_job_url,
        'status': 'RUNNING',
        'created_ts': '1454367570000000',
        'updated_ts': '1454367574000000',
    }
    report = {'isolated_tests': {step_name: [isolate_sha]}}
    mock_buildbucket.return_value = [
        (None, buildbucket_client.BuildbucketBuild(build_response))
    ]
    mock_report.return_value = report

    mock_running.return_value = {'new_param': 1}

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        revision=revision,
        urlsafe_try_job_key=try_job.key.urlsafe())

    try_job_pipeline = RunFlakeTryJobPipeline(pipeline_input)
    try_job_pipeline.start_test()
    try_job_pipeline.run(pipeline_input)

    # Reload from ID to get all internal properties in sync.
    try_job_pipeline = RunFlakeTryJobPipeline.from_id(
        try_job_pipeline.pipeline_id)
    try_job_pipeline.finalized()

    self.assertTrue(mock_update.called)

  @mock.patch.object(RunFlakeTryJobPipeline, '_TimedOut', return_value=True)
  @mock.patch.object(build_util, 'GetWaterfallBuildStepLog')
  @mock.patch.object(flake_try_job, 'ScheduleFlakeTryJob')
  @mock.patch.object(try_job_service, 'OnTryJobRunning')
  @mock.patch.object(buildbucket_client, 'GetTryJobs')
  def testCallbackTimeout(self, mock_buildbucket, mock_params, mock_schedule,
                          *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'
    revision = 'r1000'
    try_job_id = 'try_job_id'
    try_job_url = 'https://build.chromium.org/p/m/builders/b/builds/1234'

    mock_schedule.return_value = try_job_id

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

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

    build_response = {
        'id': try_job_id,
        'url': try_job_url,
        'status': 'RUNNING',
        'created_ts': '1454367570000000',
        'updated_ts': '1454367574000000',
    }

    mock_buildbucket.return_value = [
        (None, buildbucket_client.BuildbucketBuild(build_response))
    ]

    mock_params.return_value = None

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        revision=revision,
        urlsafe_try_job_key=try_job.key.urlsafe())

    with self.assertRaises(pipeline.Abort):
      try_job_pipeline = RunFlakeTryJobPipeline(pipeline_input)
      try_job_pipeline.start_test()
      try_job_pipeline.run(pipeline_input)
