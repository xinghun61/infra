# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.constants import DEFAULT_QUEUE
from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import pipeline_handlers
from services import revert
from waterfall import buildbot
from waterfall import revert_and_notify_culprit_pipeline
from waterfall.create_revert_cl_pipeline import CreateRevertCLPipeline
from waterfall.revert_and_notify_culprit_pipeline import (
    RevertAndNotifyCulpritPipeline)
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)
from waterfall.send_notification_to_irc_pipeline import (
    SendNotificationToIrcPipeline)
from waterfall.submit_revert_cl_pipeline import SubmitRevertCLPipeline
from waterfall.test import wf_testcase


class RevertAndNotifyCulpritPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(
      buildbot, 'GetBuildDataFromMilo', return_value='{"data": "data"}')
  @mock.patch.object(
      buildbot, 'GetRecentCompletedBuilds', return_value=[125, 124])
  @mock.patch.object(buildbot, 'GetBuildResult')
  def testAnyBuildSucceededPassedThenFailed(self, mock_fn, *_):
    mock_fn.side_effect = [buildbot.SUCCESS, buildbot.FAILURE]
    self.assertTrue(
        revert_and_notify_culprit_pipeline._AnyBuildSucceeded('m', 'b', 123))

  @mock.patch.object(
      buildbot, 'GetBuildDataFromMilo', return_value='{"data": "data"}')
  @mock.patch.object(
      buildbot, 'GetRecentCompletedBuilds', return_value=[125, 124])
  @mock.patch.object(buildbot, 'GetBuildResult')
  def testAnyBuildSucceeded(self, mock_fn, *_):
    mock_fn.side_effect = [buildbot.FAILURE, buildbot.FAILURE]
    self.assertFalse(
        revert_and_notify_culprit_pipeline._AnyBuildSucceeded('m', 'b', 123))

  @mock.patch.object(buildbot, 'GetBuildResult', return_value=buildbot.FAILURE)
  @mock.patch.object(
      buildbot, 'GetBuildDataFromMilo', return_value='{"data": "data"}')
  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=[124])
  def testSendNotificationForTestCulprit(self, *_):
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
    try_job_type = failure_type.TEST

    self.MockPipeline(
        SendNotificationForCulpritPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, repo_name, revision, True
        ])

    pipeline = RevertAndNotifyCulpritPipeline(master_name, builder_name,
                                              build_number, culprits,
                                              heuristic_cls, try_job_type)
    pipeline.start(queue_name=DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(buildbot, 'GetBuildResult', return_value=buildbot.FAILURE)
  @mock.patch.object(
      buildbot, 'GetBuildDataFromMilo', return_value='{"data": "data"}')
  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=[124])
  def testSendNotificationToConfirmRevert(self, *_):
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
    try_job_type = failure_type.COMPILE

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

    pipeline = RevertAndNotifyCulpritPipeline(master_name, builder_name,
                                              build_number, culprits,
                                              heuristic_cls, try_job_type)
    pipeline.start(queue_name=DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(buildbot, 'GetBuildResult', return_value=buildbot.SUCCESS)
  @mock.patch.object(
      buildbot, 'GetBuildDataFromMilo', return_value='{"data": "data"}')
  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=[125])
  @mock.patch.object(revert_and_notify_culprit_pipeline,
                     'SendNotificationForCulpritPipeline')
  def testSendNotificationLatestBuildPassed(self, mocked_pipeline, *_):
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
    try_job_type = failure_type.TEST

    pipeline = RevertAndNotifyCulpritPipeline(master_name, builder_name,
                                              build_number, culprits,
                                              heuristic_cls, try_job_type)
    pipeline.start(queue_name=DEFAULT_QUEUE)
    self.execute_queued_tasks()
    mocked_pipeline.assert_not_called()
