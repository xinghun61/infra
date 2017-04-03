# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.constants import DEFAULT_QUEUE
from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import pipeline_handlers
from waterfall import create_revert_cl_pipeline
from waterfall.create_revert_cl_pipeline import CreateRevertCLPipeline
from waterfall.revert_and_notify_culprit_pipeline import (
    RevertAndNotifyCulpritPipeline)
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.test import wf_testcase


class RevertAndNotifyCulpritPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testSendNotificationForTestCulprit(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    repo_name = 'chromium'
    revision = 'r1'
    culprits = {
        'r1': {
            'repo_name': repo_name,
            'revision': revision,
        }
    }
    heuristic_cls = [[repo_name, revision]]
    compile_suspected_cl = None
    try_job_type = failure_type.TEST

    self.MockPipeline(SendNotificationForCulpritPipeline,
                      None,
                      expected_args=[master_name, builder_name, build_number,
                                     repo_name, revision, True])

    pipeline = RevertAndNotifyCulpritPipeline(
        master_name, builder_name, build_number, culprits,
        heuristic_cls, compile_suspected_cl, try_job_type)
    pipeline.start(queue_name=DEFAULT_QUEUE)
    self.execute_queued_tasks()

  def testSendNotificationToConfirmRevert(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    repo_name = 'chromium'
    revision = 'r1'
    culprits = {
        'r1': {
            'repo_name': repo_name,
            'revision': revision,
        }
    }
    heuristic_cls = [[repo_name, revision]]
    compile_suspected_cl = None
    try_job_type = failure_type.COMPILE

    self.MockPipeline(CreateRevertCLPipeline,
                      create_revert_cl_pipeline.CREATED_BY_SHERIFF,
                      expected_args=[master_name, builder_name, build_number,
                                     repo_name, revision])
    self.MockPipeline(SendNotificationForCulpritPipeline,
                      None,
                      expected_args=[
                          master_name, builder_name, build_number, repo_name,
                          revision, True,
                          create_revert_cl_pipeline.CREATED_BY_SHERIFF])

    pipeline = RevertAndNotifyCulpritPipeline(
        master_name, builder_name, build_number, culprits,
        heuristic_cls, compile_suspected_cl, try_job_type)
    pipeline.start(queue_name=DEFAULT_QUEUE)
    self.execute_queued_tasks()

  def testSendNotificationForCompileHeuristic(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    repo_name = 'chromium'
    revision = 'r1'
    culprits = None
    heuristic_cls = [[repo_name, revision]]
    compile_suspected_cl = {
        'repo_name': repo_name,
        'revision': revision,
    }
    try_job_type = failure_type.COMPILE

    self.MockPipeline(SendNotificationForCulpritPipeline,
                      None,
                      expected_args=[
                          master_name, builder_name, build_number, repo_name,
                          revision, True])

    pipeline = RevertAndNotifyCulpritPipeline(
        master_name, builder_name, build_number, culprits,
        heuristic_cls, compile_suspected_cl, try_job_type)
    pipeline.start(queue_name=DEFAULT_QUEUE)
    self.execute_queued_tasks()
