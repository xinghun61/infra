# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import constants
from common.waterfall import failure_type
from gae_libs.pipelines import pipeline_handlers
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline
from waterfall.rerun_tryjob_pipeline import RerunTryJobPipeline
from waterfall.schedule_compile_try_job_pipeline import (
    ScheduleCompileTryJobPipeline)
from waterfall.schedule_test_try_job_pipeline import (
    ScheduleTestTryJobPipeline)
from waterfall.test import wf_testcase


class RerunTryJobPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testRerunTestTryjob(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = '1'
    good_revision = 'good'
    bad_revision = 'bad'
    suspected_revisions = ['suspected1', 'suspected2']
    tests = ['dummy_test']
    properties = {
        'good_revision': good_revision,
        'bad_revision': bad_revision,
        'suspected_revisions': suspected_revisions
    }
    additional_parameters = {'tests': tests}
    urlsafe_try_job_key = 'MockUrlSafeTryJobKey123'

    self.MockPipeline(
        ScheduleTestTryJobPipeline,
        'build_id',
        expected_args=[
            master_name, builder_name, build_number, good_revision,
            bad_revision, suspected_revisions, None, None, tests
        ],
        expected_kwargs={'force_buildbot': True})

    self.MockPipeline(
        MonitorTryJobPipeline,
        '',
        expected_args=[urlsafe_try_job_key, 'test', 'build_id'],
        expected_kwargs={})

    root_pipeline = RerunTryJobPipeline(
        master_name, builder_name, build_number, failure_type.TEST, properties,
        additional_parameters, urlsafe_try_job_key)
    root_pipeline.start(queue_name=constants.RERUN_TRYJOB_QUEUE)
    self.execute_queued_tasks()

  def testRerunCompileTryjob(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = '1'
    good_revision = 'good'
    bad_revision = 'bad'
    suspected_revisions = ['suspected1', 'suspected2']
    properties = {
        'good_revision': good_revision,
        'bad_revision': bad_revision,
        'suspected_revisions': suspected_revisions
    }
    compile_targets = ['compile_target1', 'compile_target2']
    additional_parameters = {'compile_targets': compile_targets}
    urlsafe_try_job_key = 'MockUrlSafeTryJobKey123'

    self.MockPipeline(
        ScheduleCompileTryJobPipeline,
        'build_id',
        expected_args=[
            master_name, builder_name, build_number, good_revision,
            bad_revision, compile_targets, suspected_revisions, None, None
        ],
        expected_kwargs={'force_buildbot': True})

    self.MockPipeline(
        MonitorTryJobPipeline,
        '',
        expected_args=[urlsafe_try_job_key, 'compile', 'build_id'],
        expected_kwargs={})

    root_pipeline = RerunTryJobPipeline(
        master_name, builder_name, build_number, failure_type.COMPILE,
        properties, additional_parameters, urlsafe_try_job_key)
    root_pipeline.start(queue_name=constants.RERUN_TRYJOB_QUEUE)
    self.execute_queued_tasks()

  def testRerunInvalidTryjob(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = '1'
    good_revision = 'good'
    bad_revision = 'bad'
    suspected_revisions = ['suspected1', 'suspected2']
    properties = {
        'good_revision': good_revision,
        'bad_revision': bad_revision,
        'suspected_revisions': suspected_revisions
    }
    compile_targets = ['compile_target1', 'compile_target2']
    additional_parameters = {'compile_targets': compile_targets}
    urlsafe_try_job_key = 'MockUrlSafeTryJobKey123'

    root_pipeline = RerunTryJobPipeline(
        master_name, builder_name, build_number, 'invalid', properties,
        additional_parameters, urlsafe_try_job_key)
    root_pipeline.start(queue_name=constants.RERUN_TRYJOB_QUEUE)
    self.execute_queued_tasks()
