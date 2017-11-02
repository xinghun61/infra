# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from gae_libs.pipeline_wrapper import pipeline_handlers
from pipelines.compile_failure import (
    revert_and_notify_compile_culprit_pipeline as wrapper_pipeline)
from pipelines.pipeline_inputs_and_outputs import CLKey
from pipelines.pipeline_inputs_and_outputs import CreateRevertCLPipelineInput
from pipelines.pipeline_inputs_and_outputs import SubmitRevertCLPipelineInput
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
    build_id = 'm/b/124'
    repo_name = 'chromium/test'
    revision = 'r1'
    culprits = {
        'r1': {
            'repo_name': repo_name,
            'revision': revision,
        }
    }
    heuristic_cls = [[repo_name, revision]]

    self.MockSynchronousPipeline(CreateRevertCLPipeline,
                                 CreateRevertCLPipelineInput(
                                     cl_key=CLKey(
                                         repo_name=repo_name.decode('utf-8'),
                                         revision=revision.decode('utf-8')),
                                     build_id=build_id.decode('utf-8')),
                                 revert.CREATED_BY_SHERIFF)
    self.MockSynchronousPipeline(SubmitRevertCLPipeline,
                                 SubmitRevertCLPipelineInput(
                                     cl_key=CLKey(
                                         repo_name=repo_name.decode('utf-8'),
                                         revision=revision.decode('utf-8')),
                                     revert_status=revert.CREATED_BY_SHERIFF),
                                 True)
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

  @mock.patch.object(ci_failure, 'AnyNewBuildSucceeded')
  def testFinditNotTakeActionsOnFakeMaster(self, mock_fn):
    culprits = {
        'r1': {
            'repo_name': 'chromium',
            'revision': 'r1',
        }
    }
    pipeline = wrapper_pipeline.RevertAndNotifyCompileCulpritPipeline(
        wrapper_pipeline._BYPASS_MASTER_NAME, 'b', 123, culprits, [])
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    mock_fn.assert_not_called()
