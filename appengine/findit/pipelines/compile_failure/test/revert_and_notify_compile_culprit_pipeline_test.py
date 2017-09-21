# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from gae_libs.pipeline_wrapper import pipeline_handlers
from pipelines.compile_failure import (
    revert_and_notify_compile_culprit_pipeline as wrapper_pipeline)
from services import ci_failure
from services import revert
from waterfall.create_revert_cl_pipeline import CreateRevertCLPipeline
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.send_notification_to_irc_pipeline import (
    SendNotificationToIrcPipeline)
from waterfall.submit_revert_cl_pipeline import SubmitRevertCLPipeline
from waterfall.test import wf_testcase


class RevertAndNotifyCulpritPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(ci_failure, 'AnyNewBuildSucceeded', return_value=False)
  def testSendNotificationToConfirmRevert(self, _):
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

    self.MockPipeline(
        CreateRevertCLPipeline,
        revert.CREATED_BY_SHERIFF,
        expected_args=[repo_name, revision])
    self.MockPipeline(
        SubmitRevertCLPipeline,
        True,
        expected_args=[repo_name, revision, revert.CREATED_BY_SHERIFF])
    self.MockPipeline(
        SendNotificationToIrcPipeline,
        None,
        expected_args=[repo_name, revision, revert.CREATED_BY_SHERIFF])
    self.MockPipeline(
        SendNotificationForCulpritPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, repo_name, revision, True,
            revert.CREATED_BY_SHERIFF
        ])

    pipeline = wrapper_pipeline.RevertAndNotifyCompileCulpritPipeline(
        master_name, builder_name, build_number, culprits, heuristic_cls)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(ci_failure, 'AnyNewBuildSucceeded', return_value=True)
  @mock.patch.object(wrapper_pipeline, 'SendNotificationForCulpritPipeline')
  def testSendNotificationLatestBuildPassed(self, mocked_pipeline, _):
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

    pipeline = wrapper_pipeline.RevertAndNotifyCompileCulpritPipeline(
        master_name, builder_name, build_number, culprits, heuristic_cls)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    mocked_pipeline.assert_not_called()
