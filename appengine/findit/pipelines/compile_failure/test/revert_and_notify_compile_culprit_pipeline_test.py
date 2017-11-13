# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from gae_libs.pipeline_wrapper import pipeline_handlers
from pipelines.compile_failure import (
    revert_and_notify_compile_culprit_pipeline as wrapper_pipeline)
from pipelines.pipeline_inputs_and_outputs import BuildKey
from pipelines.pipeline_inputs_and_outputs import CLKey
from pipelines.pipeline_inputs_and_outputs import CreateRevertCLPipelineInput
from pipelines.pipeline_inputs_and_outputs import DictOfCLKeys
from pipelines.pipeline_inputs_and_outputs import ListOfCLKeys
from pipelines.pipeline_inputs_and_outputs import (
    RevertAndNotifyCulpritPipelineInput)
from pipelines.pipeline_inputs_and_outputs import (
    SendNotificationToIrcPipelineInput)
from pipelines.pipeline_inputs_and_outputs import (
    SendNotificationForCulpritPipelineInput)
from pipelines.pipeline_inputs_and_outputs import SubmitRevertCLPipelineInput
from services import ci_failure
from services import gerrit
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
    cl_key = CLKey(repo_name=repo_name, revision=revision)
    culprits = DictOfCLKeys()
    culprits['r1'] = cl_key
    heuristic_cls = ListOfCLKeys()
    heuristic_cls.append(cl_key)

    self.MockSynchronousPipeline(
        CreateRevertCLPipeline,
        CreateRevertCLPipelineInput(
            cl_key=CLKey(repo_name=repo_name, revision=revision),
            build_id=build_id), gerrit.CREATED_BY_FINDIT)
    self.MockSynchronousPipeline(
        SubmitRevertCLPipeline,
        SubmitRevertCLPipelineInput(
            cl_key=CLKey(repo_name=repo_name, revision=revision),
            revert_status=gerrit.CREATED_BY_FINDIT), True)
    self.MockSynchronousPipeline(SendNotificationToIrcPipeline,
                                 SendNotificationToIrcPipelineInput(
                                     cl_key=CLKey(
                                         repo_name=repo_name,
                                         revision=revision),
                                     revert_status=gerrit.CREATED_BY_FINDIT,
                                     submitted=True), True)
    self.MockSynchronousPipeline(
        SendNotificationForCulpritPipeline,
        SendNotificationForCulpritPipelineInput(
            cl_key=CLKey(repo_name=repo_name, revision=revision),
            force_notify=True,
            revert_status=gerrit.CREATED_BY_FINDIT), True)

    pipeline = wrapper_pipeline.RevertAndNotifyCompileCulpritPipeline(
        RevertAndNotifyCulpritPipelineInput(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=culprits,
            heuristic_cls=heuristic_cls))
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
    cl_key = CLKey(repo_name=repo_name, revision=revision)
    culprits = DictOfCLKeys()
    culprits['r1'] = cl_key
    heuristic_cls = ListOfCLKeys()
    heuristic_cls.append(cl_key)

    pipeline = wrapper_pipeline.RevertAndNotifyCompileCulpritPipeline(
        RevertAndNotifyCulpritPipelineInput(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=culprits,
            heuristic_cls=heuristic_cls))
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    mocked_pipeline.assert_not_called()

  @mock.patch.object(ci_failure, 'AnyNewBuildSucceeded')
  def testFinditNotTakeActionsOnFakeMaster(self, mock_fn):
    repo_name = 'chromium'
    revision = 'r1'
    culprits = DictOfCLKeys()
    culprits['r1'] = CLKey(repo_name=repo_name, revision=revision)
    pipeline = wrapper_pipeline.RevertAndNotifyCompileCulpritPipeline(
        RevertAndNotifyCulpritPipelineInput(
            build_key=BuildKey(
                master_name=wrapper_pipeline._BYPASS_MASTER_NAME.decode(
                    'utf-8'),
                builder_name=u'b',
                build_number=123),
            culprits=culprits,
            heuristic_cls=ListOfCLKeys()))
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    mock_fn.assert_not_called()
