# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import pipeline_handlers
from model.wf_try_job import WfTryJob
from pipelines.compile_failure import (identify_compile_try_job_culprit_pipeline
                                       as culprit_pipeline)
from pipelines.compile_failure import start_compile_try_job_pipeline
from pipelines.compile_failure.start_compile_try_job_pipeline import (
    StartCompileTryJobPipeline)
from services.compile_failure import compile_try_job
from waterfall.test import wf_testcase


class StartCompileTryJobPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testNotScheduleTryJobIfBuildNotCompleted(self):
    pipeline = StartCompileTryJobPipeline()
    result = pipeline.run('m', 'b', 1, {}, {}, {}, False, False)
    self.assertEqual(list(result), [])

  @mock.patch.object(compile_try_job, 'GetParametersToScheduleCompileTryJob')
  @mock.patch.object(compile_try_job, 'NeedANewCompileTryJob')
  def testCompileTryJob(self, mock_fn, mock_parameter):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_type = failure_type.COMPILE
    failure_info = {
        'failure_type': try_job_type,
        'builds': {
            '0': {
                'blame_list': ['r0', 'r1'],
                'chromium_revision': 'r1'
            },
            '1': {
                'blame_list': ['r2'],
                'chromium_revision': 'r2'
            }
        },
        'failed_steps': {
            'compile': {
                'first_failure': 1,
                'last_pass': 0
            }
        }
    }
    good_revision = 'r1'
    bad_revision = 'r2'
    try_job = WfTryJob.Create('m', 'b', 1)
    try_job.put()

    mock_fn.return_value = True, try_job.key
    mock_parameter.return_value = {
        'good_revision': good_revision,
        'bad_revision': bad_revision,
        'compile_targets': [],
        'suspected_revisions': [],
        'cache_name': 'cache_name',
        'dimensions': []
    }

    self.MockPipeline(
        start_compile_try_job_pipeline.ScheduleCompileTryJobPipeline,
        'try_job_id',
        expected_args=[
            master_name, builder_name, build_number, good_revision,
            bad_revision, try_job_type, [], [], 'cache_name', []
        ],
        expected_kwargs={})
    self.MockPipeline(
        start_compile_try_job_pipeline.MonitorTryJobPipeline,
        'try_job_result',
        expected_args=[try_job.key.urlsafe(), try_job_type, 'try_job_id'],
        expected_kwargs={})
    self.MockPipeline(
        culprit_pipeline.IdentifyCompileTryJobCulpritPipeline,
        'final_result',
        expected_args=[
            master_name, builder_name, build_number, 'try_job_id',
            'try_job_result'
        ],
        expected_kwargs={})

    pipeline = StartCompileTryJobPipeline('m', 'b', 1, failure_info, {}, {},
                                          True, False)
    pipeline.start()
    self.execute_queued_tasks()

  @mock.patch.object(
      compile_try_job, 'NeedANewCompileTryJob', return_value=(False, None))
  @mock.patch.object(start_compile_try_job_pipeline,
                     'ScheduleCompileTryJobPipeline')
  def testNotNeedCompileTryJob(self, mock_pipeline, _):
    failure_info = {'failure_type': failure_type.COMPILE}
    pipeline = StartCompileTryJobPipeline()
    result = pipeline.run('m', 'b', 1, failure_info, {}, {}, True, False)
    self.assertEqual(list(result), [])
    mock_pipeline.assert_not_called()

  @mock.patch.object(
      compile_try_job,
      'GetParametersToScheduleCompileTryJob',
      return_value={'good_revision': None})
  @mock.patch.object(
      compile_try_job, 'NeedANewCompileTryJob', return_value=(True, None))
  @mock.patch.object(start_compile_try_job_pipeline,
                     'ScheduleCompileTryJobPipeline')
  def testNoCompileTryJobBecauseNoGoodRevision(self, mock_pipeline, *_):
    failure_info = {'failure_type': failure_type.COMPILE}
    pipeline = StartCompileTryJobPipeline()
    result = pipeline.run('m', 'b', 1, failure_info, {}, {}, True, False)
    self.assertEqual(list(result), [])
    mock_pipeline.assert_not_called()
