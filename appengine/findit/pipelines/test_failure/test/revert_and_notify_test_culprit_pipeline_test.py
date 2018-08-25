# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from common.waterfall import failure_type
from dto.dict_of_basestring import DictOfBasestring
from gae_libs.pipelines import pipeline_handlers
from libs.list_of_basestring import ListOfBasestring
from pipelines.create_revert_cl_pipeline import CreateRevertCLPipeline
from pipelines.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from pipelines.submit_revert_cl_pipeline import SubmitRevertCLPipeline
from pipelines.test_failure import revert_and_notify_test_culprit_pipeline
from pipelines.test_failure.revert_and_notify_test_culprit_pipeline import (
    RevertAndNotifyTestCulpritPipeline)
from services import ci_failure
from services import constants as services_constants
from services.parameters import BuildKey
from services.parameters import CreateRevertCLParameters
from services.parameters import CulpritActionParameters
from services.parameters import FailureToCulpritMap
from services.parameters import SendNotificationForCulpritParameters
from services.parameters import SubmitRevertCLParameters
from services.test_failure import test_culprit_action
from waterfall.test import wf_testcase


class RevertAndNotifyTestCulpritPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(
      test_culprit_action, 'CanAutoCreateRevert', return_value=False)
  @mock.patch.object(
      test_culprit_action, 'CanAutoCommitRevertByFindit', return_value=False)
  @mock.patch.object(
      ci_failure,
      'GetLaterBuildsWithAnySameStepFailure',
      return_value={125: ['a']})
  def testSendNotificationForTestCulpritNoRevert(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    cl_key = 'mockurlsafekey'
    culprits = DictOfBasestring()
    culprits['r1'] = cl_key
    heuristic_cls = ListOfBasestring()
    heuristic_cls.append(cl_key)

    failure_to_culprit_map = FailureToCulpritMap.FromSerializable({
        'step1': {
            't1': 'r1'
        }
    })

    input_object = SendNotificationForCulpritParameters(
        cl_key=cl_key,
        force_notify=True,
        revert_status=services_constants.SKIPPED,
        failure_type=failure_type.TEST)
    self.MockSynchronousPipeline(SendNotificationForCulpritPipeline,
                                 input_object, True)

    pipeline = RevertAndNotifyTestCulpritPipeline(
        CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=culprits,
            heuristic_cls=heuristic_cls,
            failure_to_culprit_map=failure_to_culprit_map))
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(
      ci_failure, 'GetLaterBuildsWithAnySameStepFailure', return_value=[])
  @mock.patch.object(revert_and_notify_test_culprit_pipeline,
                     'SendNotificationForCulpritPipeline')
  def testSendNotificationLatestBuildPassed(self, mocked_pipeline, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    cl_key = 'mockurlsafekey'
    culprits = DictOfBasestring()
    culprits['r1'] = cl_key
    heuristic_cls = ListOfBasestring()
    heuristic_cls.append(cl_key)
    failure_to_culprit_map = FailureToCulpritMap.FromSerializable({
        'step1': {
            't1': 'r1'
        }
    })

    pipeline = RevertAndNotifyTestCulpritPipeline(
        CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=culprits,
            heuristic_cls=heuristic_cls,
            failure_to_culprit_map=failure_to_culprit_map))
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    self.assertFalse(mocked_pipeline.called)

  @mock.patch.object(
      test_culprit_action, 'GetCulpritsShouldTakeActions', return_value=['r1'])
  @mock.patch.object(
      test_culprit_action, 'CanAutoCreateRevert', return_value=True)
  @mock.patch.object(
      test_culprit_action, 'CanAutoCommitRevertByFindit', return_value=True)
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
    failure_to_culprit_map = FailureToCulpritMap.FromSerializable({
        'step1': {
            't1': 'r1'
        }
    })

    self.MockSynchronousPipeline(
        CreateRevertCLPipeline,
        CreateRevertCLParameters(
            cl_key=cl_key, build_id=build_id, failure_type=failure_type.TEST),
        services_constants.CREATED_BY_FINDIT)
    self.MockSynchronousPipeline(
        SubmitRevertCLPipeline,
        SubmitRevertCLParameters(
            cl_key=cl_key,
            revert_status=services_constants.CREATED_BY_FINDIT,
            failure_type=failure_type.TEST), services_constants.COMMITTED)
    self.MockSynchronousPipeline(
        SendNotificationForCulpritPipeline,
        SendNotificationForCulpritParameters(
            cl_key=cl_key,
            force_notify=True,
            revert_status=services_constants.CREATED_BY_FINDIT,
            failure_type=failure_type.TEST), True)

    pipeline = RevertAndNotifyTestCulpritPipeline(
        CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=culprits,
            heuristic_cls=heuristic_cls,
            failure_to_culprit_map=failure_to_culprit_map))
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(
      test_culprit_action, 'GetCulpritsShouldTakeActions', return_value=['r1'])
  @mock.patch.object(
      test_culprit_action, 'CanAutoCreateRevert', return_value=True)
  @mock.patch.object(
      test_culprit_action, 'CanAutoCommitRevertByFindit', return_value=False)
  def testCreatedRevertButNotCommitted(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    build_id = 'm/b/124'

    cl_key = 'mockurlsafekey'
    culprits = DictOfBasestring()
    culprits['r1'] = cl_key
    heuristic_cls = ListOfBasestring()
    heuristic_cls.append(cl_key)
    failure_to_culprit_map = FailureToCulpritMap.FromSerializable({
        'step1': {
            't1': 'r1'
        }
    })

    self.MockSynchronousPipeline(
        CreateRevertCLPipeline,
        CreateRevertCLParameters(
            cl_key=cl_key, build_id=build_id, failure_type=failure_type.TEST),
        services_constants.CREATED_BY_FINDIT)
    self.MockSynchronousPipeline(
        SendNotificationForCulpritPipeline,
        SendNotificationForCulpritParameters(
            cl_key=cl_key,
            force_notify=True,
            revert_status=services_constants.CREATED_BY_FINDIT,
            failure_type=failure_type.TEST), True)

    pipeline = RevertAndNotifyTestCulpritPipeline(
        CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=culprits,
            heuristic_cls=heuristic_cls,
            failure_to_culprit_map=failure_to_culprit_map))
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
