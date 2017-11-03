# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from gae_libs.pipeline_wrapper import pipeline_handlers
from pipelines.pipeline_inputs_and_outputs import CLKey
from pipelines.pipeline_inputs_and_outputs import (
    SendNotificationForCulpritPipelineInput)
from pipelines.test_failure import revert_and_notify_test_culprit_pipeline
from pipelines.test_failure.revert_and_notify_test_culprit_pipeline import (
    RevertAndNotifyTestCulpritPipeline)
from services import ci_failure
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.test import wf_testcase


class RevertAndNotifyTestCulpritPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(ci_failure, 'AnyNewBuildSucceeded', return_value=False)
  def testSendNotificationForTestCulprit(self, _):
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

    self.MockSynchronousPipeline(SendNotificationForCulpritPipeline,
                                 SendNotificationForCulpritPipelineInput(
                                     cl_key=CLKey(
                                         repo_name=repo_name.decode('utf-8'),
                                         revision=revision.decode('utf-8')),
                                     force_notify=True,
                                     revert_status=None),
                                 True)

    pipeline = RevertAndNotifyTestCulpritPipeline(master_name, builder_name,
                                                  build_number, culprits,
                                                  heuristic_cls)
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
    culprits = {
        'r1': {
            'repo_name': repo_name,
            'revision': revision,
        }
    }
    heuristic_cls = [[repo_name, revision]]

    pipeline = RevertAndNotifyTestCulpritPipeline(master_name, builder_name,
                                                  build_number, culprits,
                                                  heuristic_cls)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    mocked_pipeline.assert_not_called()
