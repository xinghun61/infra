# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from gae_libs.testcase import TestCase
from model.flake.flake_try_job import FlakeTryJob
from model.flake.flake_try_job_data import FlakeTryJobData
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from services.flake_failure import flake_try_job_service
from waterfall.flake.process_flake_try_job_result_pipeline import (
    ProcessFlakeTryJobResultPipeline)


class ProcessFlakeTryJobResultPipelineTest(TestCase):

  @mock.patch.object(
      flake_try_job_service, 'IsTryJobResultValid', return_value=True)
  @mock.patch.object(flake_try_job_service, 'GetSwarmingTaskIdForTryJob')
  def testProcessFlakeTryJobResultPipeline(self, mocked_get_swarming_task, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    revision = 'r4'
    commit_position = 4
    try_job_id = 'try_job_id'
    swarming_task_id = 'swarming_task_id'
    mocked_get_swarming_task.return_value = swarming_task_id
    url = 'url'
    try_job_result = {
        'result': {
            revision: {
                step_name: {
                    'status': 'failed',
                    'failures': [test_name],
                    'valid': True,
                    'pass_fail_counts': {
                        test_name: {
                            'pass_count': 20,
                            'fail_count': 80
                        }
                    }
                }
            }
        }
    }
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()
    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.flake_results = [{
        'url': url,
        'report': try_job_result,
        'try_job_id': try_job_id
    }]
    try_job.try_job_ids = [try_job_id]
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.start_time = datetime(2017, 10, 13, 13, 0, 0)
    try_job_data.end_time = datetime(2017, 10, 13, 14, 0, 0)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    ProcessFlakeTryJobResultPipeline().run(revision, commit_position,
                                           try_job.key.urlsafe(),
                                           analysis.key.urlsafe())

    resulting_data_point = analysis.data_points[-1]

    self.assertEqual(0.2, resulting_data_point.pass_rate)
    self.assertEqual(commit_position, resulting_data_point.commit_position)
    self.assertEqual(url, resulting_data_point.try_job_url)
    self.assertEqual(3600, resulting_data_point.elapsed_seconds)
    self.assertEqual([swarming_task_id], resulting_data_point.task_ids)

  @mock.patch.object(
      flake_try_job_service, 'IsTryJobResultValid', return_value=False)
  def testProcessFlakeTryJobResultPipelineInvalidResult(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    revision = 'r4'
    commit_position = 4
    try_job_id = 'try_job_id'
    url = 'url'
    try_job_result = {
        'result': {
            revision: {
                step_name: {
                    'status': 'failed',
                    'failures': [test_name],
                    'valid': False,
                    'pass_fail_counts': {}
                }
            }
        }
    }
    expected_error = {
        'message': 'Try job results are not valid',
        'reason': 'Try job results are not vaild',
    }
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()
    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.flake_results = [{
        'url': url,
        'report': try_job_result,
        'try_job_id': try_job_id
    }]
    try_job.try_job_ids = [try_job_id]
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.start_time = datetime(2017, 10, 13, 13, 0, 0)
    try_job_data.end_time = datetime(2017, 10, 13, 14, 0, 0)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    ProcessFlakeTryJobResultPipeline().run(revision, commit_position,
                                           try_job.key.urlsafe(),
                                           analysis.key.urlsafe())

    self.assertEqual(expected_error, try_job.error)
    self.assertEqual([], analysis.data_points)

  def testProcessFlakeTryJobResultPipelineTryJobFailed(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    revision = 'r4'
    commit_position = 4
    try_job_id = 'try_job_id'
    url = 'url'
    try_job_result = {'result': {revision: 'infra failed'}}
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()
    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.flake_results = [{
        'url': url,
        'report': try_job_result,
        'try_job_id': try_job_id
    }]
    try_job.try_job_ids = [try_job_id]
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.start_time = datetime(2017, 10, 13, 13, 0, 0)
    try_job_data.end_time = datetime(2017, 10, 13, 14, 0, 0)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    ProcessFlakeTryJobResultPipeline().run(revision, commit_position,
                                           try_job.key.urlsafe(),
                                           analysis.key.urlsafe())

    self.assertEqual([], analysis.data_points)
