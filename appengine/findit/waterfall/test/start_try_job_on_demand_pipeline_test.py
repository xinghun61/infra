# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.waterfall import failure_type
from model.wf_try_job import WfTryJob
from services.compile_failure import compile_try_job
from services.test_failure import test_try_job
from waterfall import start_try_job_on_demand_pipeline
from waterfall.start_try_job_on_demand_pipeline import (
    StartTryJobOnDemandPipeline)
from waterfall.test import wf_testcase


class StartTryJobOnDemandPipelineTest(wf_testcase.WaterfallTestCase):

  def testNotScheduleTryJobIfBuildNotCompleted(self):
    pipeline = start_try_job_on_demand_pipeline.StartTryJobOnDemandPipeline()
    result = pipeline.run('m', 'b', 1, {}, {}, {}, False, False)
    self.assertEqual(list(result), [])

  def testNotScheduleTryJobIfUnsupportedFailureType(self):
    try_job_type = failure_type.UNKNOWN
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
            'a': {
                'first_failure': 1,
                'last_pass': 0
            }
        }
    }
    pipeline = start_try_job_on_demand_pipeline.StartTryJobOnDemandPipeline()
    result = pipeline.run('m', 'b', 1, failure_info, {}, {}, True, False)
    self.assertEqual(list(result), [])

  @mock.patch.object(compile_try_job, 'NeedANewCompileTryJob')
  def testCompileTryJob(self, mock_fn):
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

    self.MockPipeline(
        start_try_job_on_demand_pipeline.ScheduleCompileTryJobPipeline,
        'try_job_id',
        expected_args=[
            master_name, builder_name, build_number, good_revision,
            bad_revision, try_job_type, {}, []
        ],
        expected_kwargs={})
    self.MockPipeline(
        start_try_job_on_demand_pipeline.MonitorTryJobPipeline,
        'try_job_result',
        expected_args=[try_job.key.urlsafe(), try_job_type, 'try_job_id'],
        expected_kwargs={})
    self.MockPipeline(
        start_try_job_on_demand_pipeline.IdentifyTryJobCulpritPipeline,
        'final_result',
        expected_args=[
            master_name, builder_name, build_number, ['r2'], try_job_type,
            'try_job_id', 'try_job_result'
        ],
        expected_kwargs={})

    pipeline = StartTryJobOnDemandPipeline()
    result = pipeline.run('m', 'b', 1, failure_info, {}, {}, True, False)
    self.assertNotEqual(list(result), [])

  @mock.patch.object(
      compile_try_job, 'NeedANewCompileTryJob', return_value=(False, None))
  @mock.patch.object(start_try_job_on_demand_pipeline,
                     'ScheduleCompileTryJobPipeline')
  def testNotNeedCompileTryJob(self, mock_pipeline, _):
    failure_info = {'failure_type': failure_type.COMPILE}
    pipeline = StartTryJobOnDemandPipeline()
    result = pipeline.run('m', 'b', 1, failure_info, {}, {}, True, False)
    self.assertEqual(list(result), [])
    mock_pipeline.assert_not_called()

  @mock.patch.object(
      compile_try_job,
      'GetParametersToScheduleCompileTryJob',
      return_value={'good_revision': None})
  @mock.patch.object(
      compile_try_job, 'NeedANewCompileTryJob', return_value=(True, None))
  @mock.patch.object(start_try_job_on_demand_pipeline,
                     'ScheduleCompileTryJobPipeline')
  def testNoCompileTryJobBecauseNoGoodRevision(self, mock_pipeline, *_):
    failure_info = {'failure_type': failure_type.COMPILE}
    pipeline = StartTryJobOnDemandPipeline()
    result = pipeline.run('m', 'b', 1, failure_info, {}, {}, True, False)
    self.assertEqual(list(result), [])
    mock_pipeline.assert_not_called()

  @mock.patch.object(test_try_job, 'NeedANewTestTryJob')
  def testTestTryJob(self, mock_fn):
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

    self.MockPipeline(
        start_try_job_on_demand_pipeline.ScheduleTestTryJobPipeline,
        'try_job_id',
        expected_args=[
            master_name, builder_name, build_number, good_revision,
            bad_revision, try_job_type, 'targeted_tests', []
        ],
        expected_kwargs={})
    self.MockPipeline(
        start_try_job_on_demand_pipeline.MonitorTryJobPipeline,
        'try_job_result',
        expected_args=[try_job.key.urlsafe(), try_job_type, 'try_job_id'],
        expected_kwargs={})
    self.MockPipeline(
        start_try_job_on_demand_pipeline.IdentifyTryJobCulpritPipeline,
        'final_result',
        expected_args=[
            master_name, builder_name, build_number, ['r2'], try_job_type,
            'try_job_id', 'try_job_result'
        ],
        expected_kwargs={})

    pipeline = StartTryJobOnDemandPipeline()
    result = pipeline.run('m', 'b', 1, failure_info, {}, {}, True, False)
    self.assertNotEqual(list(result), [])

  @mock.patch.object(
      test_try_job, 'NeedANewTestTryJob', return_value=(False, None))
  @mock.patch.object(start_try_job_on_demand_pipeline,
                     'ScheduleTestTryJobPipeline')
  def testNotNeedTestTryJob(self, mock_pipeline, _):
    failure_info = {'failure_type': failure_type.TEST}
    pipeline = StartTryJobOnDemandPipeline()
    result = pipeline.run('m', 'b', 1, failure_info, {}, {}, True, False)
    self.assertEqual(list(result), [])
    mock_pipeline.assert_has_called()

  @mock.patch.object(
      test_try_job,
      'GetParametersToScheduleTestTryJob',
      return_value={'good_revision': None})
  @mock.patch.object(
      test_try_job, 'NeedANewTestTryJob', return_value=(True, None))
  @mock.patch.object(start_try_job_on_demand_pipeline,
                     'ScheduleTestTryJobPipeline')
  def testNoTestTryJobBecauseNoGoodRevision(self, mock_pipeline, *_):
    failure_info = {'failure_type': failure_type.TEST}
    pipeline = StartTryJobOnDemandPipeline()
    result = pipeline.run('m', 'b', 1, failure_info, {}, {}, True, False)
    self.assertEqual(list(result), [])
    mock_pipeline.assert_not_called()
