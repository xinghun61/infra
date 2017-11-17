# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from gae_libs.pipelines import pipeline_handlers
from pipelines.compile_failure import (
    revert_and_notify_compile_culprit_pipeline as wrapper_pipeline)
from services import ci_failure
from services import gerrit
from services.compile_failure import compile_culprit_action
from services.parameters import BuildKey
from services.parameters import CLKey
from services.parameters import CreateRevertCLParameters
from services.parameters import CulpritActionParameters
from services.parameters import DictOfCLKeys
from services.parameters import ListOfCLKeys
from services.parameters import SendNotificationToIrcParameters
from services.parameters import SendNotificationForCulpritParameters
from services.parameters import SubmitRevertCLParameters
from waterfall.create_revert_cl_pipeline import CreateRevertCLPipeline
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.send_notification_to_irc_pipeline import (
    SendNotificationToIrcPipeline)
from waterfall.submit_revert_cl_pipeline import SubmitRevertCLPipeline
from waterfall.test import wf_testcase


class RevertAndNotifyCulpritPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(
      compile_culprit_action, 'ShouldTakeActionsOnCulprit', return_value=True)
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
        CreateRevertCLParameters(
            cl_key=CLKey(repo_name=repo_name, revision=revision),
            build_id=build_id), gerrit.CREATED_BY_FINDIT)
    self.MockSynchronousPipeline(
        SubmitRevertCLPipeline,
        SubmitRevertCLParameters(
            cl_key=CLKey(repo_name=repo_name, revision=revision),
            revert_status=gerrit.CREATED_BY_FINDIT), True)
    self.MockSynchronousPipeline(SendNotificationToIrcPipeline,
                                 SendNotificationToIrcParameters(
                                     cl_key=CLKey(
                                         repo_name=repo_name,
                                         revision=revision),
                                     revert_status=gerrit.CREATED_BY_FINDIT,
                                     submitted=True), True)
    self.MockSynchronousPipeline(
        SendNotificationForCulpritPipeline,
        SendNotificationForCulpritParameters(
            cl_key=CLKey(repo_name=repo_name, revision=revision),
            force_notify=True,
            revert_status=gerrit.CREATED_BY_FINDIT), True)

    pipeline = wrapper_pipeline.RevertAndNotifyCompileCulpritPipeline(
        CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=culprits,
            heuristic_cls=heuristic_cls))
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(
      compile_culprit_action, 'ShouldTakeActionsOnCulprit', return_value=False)
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
        CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=culprits,
            heuristic_cls=heuristic_cls))
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    mocked_pipeline.assert_not_called()
