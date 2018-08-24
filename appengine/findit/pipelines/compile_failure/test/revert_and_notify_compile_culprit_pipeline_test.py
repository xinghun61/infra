# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from common.waterfall import failure_type
from dto.dict_of_basestring import DictOfBasestring
from gae_libs.pipelines import pipeline_handlers
from libs.list_of_basestring import ListOfBasestring
from pipelines.compile_failure import (
    revert_and_notify_compile_culprit_pipeline as wrapper_pipeline)
from pipelines.create_revert_cl_pipeline import CreateRevertCLPipeline
from pipelines.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from pipelines.submit_revert_cl_pipeline import SubmitRevertCLPipeline
from services import constants as services_constants
from services.compile_failure import compile_culprit_action
from services.parameters import BuildKey
from services.parameters import CreateRevertCLParameters
from services.parameters import CulpritActionParameters
from services.parameters import SendNotificationToIrcParameters
from services.parameters import SendNotificationForCulpritParameters
from services.parameters import SubmitRevertCLParameters
from waterfall.send_notification_to_irc_pipeline import (
    SendNotificationToIrcPipeline)
from waterfall.test import wf_testcase


class RevertAndNotifyCulpritPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(
      compile_culprit_action, 'ShouldTakeActionsOnCulprit', return_value=True)
  @mock.patch.object(
      compile_culprit_action, 'CanAutoCreateRevert', return_value=True)
  @mock.patch.object(
      compile_culprit_action, 'CanAutoCommitRevertByFindit', return_value=True)
  def testSendNotificationToConfirmRevert(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    build_id = 'm/b/124'

    cl_key = 'mockurlsafekey'
    culprits = DictOfBasestring()
    culprits['r1'] = cl_key
    heuristic_cls = ListOfBasestring()
    heuristic_cls.append(cl_key)

    self.MockSynchronousPipeline(
        CreateRevertCLPipeline,
        CreateRevertCLParameters(
            cl_key=cl_key, build_id=build_id,
            failure_type=failure_type.COMPILE),
        services_constants.CREATED_BY_FINDIT)
    self.MockSynchronousPipeline(
        SubmitRevertCLPipeline,
        SubmitRevertCLParameters(
            cl_key=cl_key,
            revert_status=services_constants.CREATED_BY_FINDIT,
            failure_type=failure_type.COMPILE), services_constants.COMMITTED)
    self.MockSynchronousPipeline(
        SendNotificationToIrcPipeline,
        SendNotificationToIrcParameters(
            cl_key=cl_key,
            revert_status=services_constants.CREATED_BY_FINDIT,
            commit_status=services_constants.COMMITTED,
            failure_type=failure_type.COMPILE), True)
    self.MockSynchronousPipeline(
        SendNotificationForCulpritPipeline,
        SendNotificationForCulpritParameters(
            cl_key=cl_key,
            force_notify=True,
            revert_status=services_constants.CREATED_BY_FINDIT,
            failure_type=failure_type.COMPILE), True)

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
      compile_culprit_action, 'ShouldTakeActionsOnCulprit', return_value=True)
  @mock.patch.object(
      compile_culprit_action, 'CanAutoCreateRevert', return_value=True)
  @mock.patch.object(
      compile_culprit_action, 'CanAutoCommitRevertByFindit', return_value=False)
  def testCreatedRevertButNotSubmitted(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    build_id = 'm/b/124'

    cl_key = "mockurlsafekey"

    culprits = DictOfBasestring()
    culprits['r1'] = cl_key

    heuristic_cls = ListOfBasestring()
    heuristic_cls.append(cl_key)

    self.MockSynchronousPipeline(
        CreateRevertCLPipeline,
        CreateRevertCLParameters(
            cl_key=cl_key, build_id=build_id,
            failure_type=failure_type.COMPILE),
        services_constants.CREATED_BY_FINDIT)
    self.MockSynchronousPipeline(
        SendNotificationToIrcPipeline,
        SendNotificationToIrcParameters(
            cl_key=cl_key,
            revert_status=services_constants.CREATED_BY_FINDIT,
            commit_status=services_constants.SKIPPED,
            failure_type=failure_type.COMPILE), True)
    self.MockSynchronousPipeline(
        SendNotificationForCulpritPipeline,
        SendNotificationForCulpritParameters(
            cl_key=cl_key,
            force_notify=True,
            revert_status=services_constants.CREATED_BY_FINDIT,
            failure_type=failure_type.COMPILE), True)

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
      compile_culprit_action, 'ShouldTakeActionsOnCulprit', return_value=True)
  @mock.patch.object(
      compile_culprit_action, 'CanAutoCreateRevert', return_value=False)
  def testNotAutoRevert(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    cl_key = 'mockurlsafekey'
    culprits = DictOfBasestring()
    culprits['r1'] = cl_key
    heuristic_cls = ListOfBasestring()
    heuristic_cls.append(cl_key)

    self.MockSynchronousPipeline(
        SendNotificationToIrcPipeline,
        SendNotificationToIrcParameters(
            cl_key=cl_key,
            revert_status=services_constants.SKIPPED,
            commit_status=services_constants.SKIPPED,
            failure_type=failure_type.COMPILE), True)
    self.MockSynchronousPipeline(
        SendNotificationForCulpritPipeline,
        SendNotificationForCulpritParameters(
            cl_key=cl_key,
            force_notify=True,
            revert_status=services_constants.SKIPPED,
            failure_type=failure_type.COMPILE), True)

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

    cl_key = 'mockurlsafekey'
    culprits = DictOfBasestring()
    culprits['r1'] = cl_key
    heuristic_cls = ListOfBasestring()
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
    self.assertFalse(mocked_pipeline.called)
