# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.waterfall import failure_type
from gae_libs.pipelines import pipeline_handlers
from model.wf_try_job import WfTryJob
from pipelines.test_failure import start_test_try_job_pipeline
from pipelines.test_failure.start_test_try_job_pipeline import (
    StartTestTryJobPipeline)
from services.parameters import BuildKey
from services.parameters import ScheduleTestTryJobParameters
from services.test_failure import test_try_job
from waterfall.test import wf_testcase


class StartTestTryJobPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testNotScheduleTryJobIfBuildNotCompleted(self):
    pipeline = start_test_try_job_pipeline.StartTestTryJobPipeline()
    result = pipeline.run('m', 'b', 1, {}, {}, False, False)
    self.assertEqual(list(result), [])

  @mock.patch.object(test_try_job, 'GetParametersToScheduleTestTryJob')
  @mock.patch.object(test_try_job, 'NeedANewTestTryJob')
  def testTestTryJob(self, mock_fn, mock_parameter):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_type = failure_type.TEST
    failure_info = {
        'parent_mastername': None,
        'parent_buildername': None,
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
            'a': {
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'test1': {
                        'first_failure': 1,
                        'last_pass': 0
                    },
                    'test2': {
                        'first_failure': 0
                    }
                }
            },
            'b': {
                'first_failure': 0,
                'tests': {
                    'b_test1': {
                        'first_failure': 0
                    }
                }
            }
        }
    }
    good_revision = 'r1'
    bad_revision = 'r2'
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.put()
    mock_fn.return_value = (True, try_job.key)
    parameters = ScheduleTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        bad_revision=bad_revision,
        good_revision=good_revision,
        suspected_revisions=[],
        targeted_tests={'step': ['test']},
        dimensions=[],
        cache_name=None,
        force_buildbot=False)
    mock_parameter.return_value = parameters

    self.MockSynchronousPipeline(
        start_test_try_job_pipeline.ScheduleTestTryJobPipeline, parameters,
        'try_job_id')
    self.MockPipeline(
        start_test_try_job_pipeline.MonitorTryJobPipeline,
        'try_job_result',
        expected_args=[try_job.key.urlsafe(), try_job_type, 'try_job_id'],
        expected_kwargs={})
    self.MockPipeline(
        start_test_try_job_pipeline.IdentifyTestTryJobCulpritPipeline,
        'final_result',
        expected_args=[
            master_name, builder_name, build_number, 'try_job_id',
            'try_job_result'
        ],
        expected_kwargs={})

    pipeline = StartTestTryJobPipeline('m', 'b', 1, failure_info, {}, True,
                                       False)
    pipeline.start()
    self.execute_queued_tasks()

  @mock.patch.object(
      test_try_job, 'NeedANewTestTryJob', return_value=(False, None))
  @mock.patch.object(start_test_try_job_pipeline, 'ScheduleTestTryJobPipeline')
  def testNotNeedTestTryJob(self, mock_pipeline, _):
    failure_info = {'failure_type': failure_type.TEST}
    pipeline = StartTestTryJobPipeline()
    result = pipeline.run('m', 'b', 1, failure_info, {}, True, False)
    self.assertEqual(list(result), [])
    mock_pipeline.assert_not_called()

  @mock.patch.object(
      test_try_job, 'NeedANewTestTryJob', return_value=(True, None))
  @mock.patch.object(test_try_job, 'GetParametersToScheduleTestTryJob')
  @mock.patch.object(start_test_try_job_pipeline, 'ScheduleTestTryJobPipeline')
  def testNoTestTryJobBecauseNoGoodRevision(self, mock_pipeline, mock_parameter,
                                            _):
    failure_info = {'failure_type': failure_type.TEST}
    mock_parameter.return_value = ScheduleTestTryJobParameters(
        good_revision=None)
    pipeline = StartTestTryJobPipeline()
    result = pipeline.run('m', 'b', 1, failure_info, {}, True, False)
    self.assertEqual(list(result), [])
    mock_pipeline.assert_not_called()

  @mock.patch.object(
      test_try_job, 'NeedANewTestTryJob', return_value=(True, None))
  @mock.patch.object(test_try_job, 'GetParametersToScheduleTestTryJob')
  @mock.patch.object(start_test_try_job_pipeline, 'ScheduleTestTryJobPipeline')
  def testNoTestTryJobBecauseNoTargetedTests(self, mock_pipeline,
                                             mock_parameter, _):
    failure_info = {'failure_type': failure_type.TEST}
    mock_parameter.return_value = ScheduleTestTryJobParameters(
        targeted_tests={}, good_revision='rev1')
    pipeline = StartTestTryJobPipeline()
    result = pipeline.run('m', 'b', 1, failure_info, {}, True, False)
    self.assertEqual(list(result), [])
    mock_pipeline.assert_not_called()
