# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from common.waterfall import failure_type
from gae_libs.pipelines import pipeline_handlers
from pipelines.create_revert_cl_pipeline import CreateRevertCLPipeline
from pipelines.submit_revert_cl_pipeline import SubmitRevertCLPipeline
from pipelines.test_failure import revert_and_notify_test_culprit_pipeline
from pipelines.test_failure.revert_and_notify_test_culprit_pipeline import (
    RevertAndNotifyTestCulpritPipeline)
from services import ci_failure
from services import culprit_action
from services import gerrit
from services.parameters import BuildKey
from services.parameters import CLKey
from services.parameters import CreateRevertCLParameters
from services.parameters import CulpritActionParameters
from services.parameters import DictOfCLKeys
from services.parameters import ListOfCLKeys
from services.parameters import SendNotificationForCulpritParameters
from services.parameters import SubmitRevertCLParameters
from services.test_failure import test_culprit_action
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.test import wf_testcase


class RevertAndNotifyTestCulpritPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(
      test_culprit_action, 'CanAutoCreateRevert', return_value=False)
  @mock.patch.object(
      test_culprit_action, 'CanAutoCommitRevertByFindit', return_value=False)
  @mock.patch.object(ci_failure, 'AnyNewBuildSucceeded', return_value=False)
  @mock.patch.object(revert_and_notify_test_culprit_pipeline,
                     'CreateInputObjectInstance')
  def testSendNotificationForTestCulpritNoRevert(self, mock_input, *_):
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

    input_object = SendNotificationForCulpritParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        force_notify=True,
        revert_status=None,
        failure_type=failure_type.TEST)
    mock_input.return_value = input_object
    self.MockSynchronousPipeline(SendNotificationForCulpritPipeline,
                                 input_object, True)

    pipeline = RevertAndNotifyTestCulpritPipeline(
        CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=culprits,
            heuristic_cls=heuristic_cls))
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(ci_failure, 'AnyNewBuildSucceeded', return_value=True)
  @mock.patch.object(revert_and_notify_test_culprit_pipeline,
                     'SendNotificationForCulpritPipeline')
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

    pipeline = RevertAndNotifyTestCulpritPipeline(
        CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=culprits,
            heuristic_cls=heuristic_cls))
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    self.assertFalse(mocked_pipeline.called)

  @mock.patch.object(
      culprit_action, 'ShouldTakeActionsOnCulprit', return_value=True)
  @mock.patch.object(
      test_culprit_action, 'CanAutoCreateRevert', return_value=True)
  @mock.patch.object(
      test_culprit_action, 'CanAutoCommitRevertByFindit', return_value=True)
  def testSendNotificationToConfirmRevert(self, *_):
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
            build_id=build_id,
            failure_type=failure_type.TEST), gerrit.CREATED_BY_FINDIT)
    self.MockSynchronousPipeline(
        SubmitRevertCLPipeline,
        SubmitRevertCLParameters(
            cl_key=CLKey(repo_name=repo_name, revision=revision),
            revert_status=gerrit.CREATED_BY_FINDIT,
            failure_type=failure_type.TEST), gerrit.COMMITTED)
    self.MockSynchronousPipeline(SendNotificationForCulpritPipeline,
                                 SendNotificationForCulpritParameters(
                                     cl_key=CLKey(
                                         repo_name=repo_name,
                                         revision=revision),
                                     force_notify=True,
                                     revert_status=gerrit.CREATED_BY_FINDIT,
                                     failure_type=failure_type.TEST), True)

    pipeline = RevertAndNotifyTestCulpritPipeline(
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
      culprit_action, 'ShouldTakeActionsOnCulprit', return_value=True)
  @mock.patch.object(
      test_culprit_action, 'CanAutoCreateRevert', return_value=True)
  @mock.patch.object(
      test_culprit_action, 'CanAutoCommitRevertByFindit', return_value=False)
  def testCreatedRevertButNotCommitted(self, *_):
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
            build_id=build_id,
            failure_type=failure_type.TEST), gerrit.CREATED_BY_FINDIT)
    self.MockSynchronousPipeline(SendNotificationForCulpritPipeline,
                                 SendNotificationForCulpritParameters(
                                     cl_key=CLKey(
                                         repo_name=repo_name,
                                         revision=revision),
                                     force_notify=True,
                                     revert_status=gerrit.CREATED_BY_FINDIT,
                                     failure_type=failure_type.TEST), True)

    pipeline = RevertAndNotifyTestCulpritPipeline(
        CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=culprits,
            heuristic_cls=heuristic_cls))
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
