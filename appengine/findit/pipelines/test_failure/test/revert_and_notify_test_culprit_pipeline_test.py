# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from gae_libs.pipeline_wrapper import pipeline_handlers
from pipelines.test_failure import revert_and_notify_test_culprit_pipeline
from pipelines.test_failure.revert_and_notify_test_culprit_pipeline import (
    RevertAndNotifyTestCulpritPipeline)
from services import ci_failure
from services.parameters import BuildKey
from services.parameters import CLKey
from services.parameters import CulpritActionParameters
from services.parameters import DictOfCLKeys
from services.parameters import ListOfCLKeys
from services.parameters import SendNotificationForCulpritParameters
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.test import wf_testcase


class RevertAndNotifyTestCulpritPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(ci_failure, 'AnyNewBuildSucceeded', return_value=False)
  @mock.patch.object(revert_and_notify_test_culprit_pipeline,
                     'CreateInputObjectInstance')
  def testSendNotificationForTestCulprit(self, mock_input, _):
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
        revert_status=None)
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
    cl_key = CLKey(repo_name=repo_name.decode('utf=8'), revision=revision)
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
    mocked_pipeline.assert_not_called()
