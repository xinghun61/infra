# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from google.appengine.ext import ndb

from gae_libs.pipeline_wrapper import pipeline_handlers
from infra_api_clients.codereview import codereview_util
from infra_api_clients.codereview import codereview
from libs import analysis_status
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import suspected_cl_util
from waterfall.flake import send_notification_for_flake_culprit_pipeline
from waterfall.flake.send_notification_for_flake_culprit_pipeline import (
    SendNotificationForFlakeCulpritPipeline)
from waterfall.test import wf_testcase


class SendNotificationForFlakeCulpritPipelineTest(
    wf_testcase.WaterfallTestCase):

  app_module = pipeline_handlers._APP

  def testShouldSendNotificationConfigSetFalse(self):
    action_settings = {'cr_notification_should_notify_flake_culprit': False}

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.put()

    self.assertFalse(
        send_notification_for_flake_culprit_pipeline._ShouldSendNotification(
            analysis, action_settings))

  def testShouldSendNotificationAlreadyProcessed(self):
    repo_name = 'repo'
    revision = 'r1'
    url = 'code.review.url'
    commit_position = 1000

    action_settings = {'cr_notification_should_notify_flake_culprit': True}

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')

    culprit = FlakeCulprit.Create(repo_name, revision, commit_position, url)
    culprit.cr_notification_status = analysis_status.COMPLETED
    culprit.put()
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    self.assertFalse(
        send_notification_for_flake_culprit_pipeline._ShouldSendNotification(
            analysis, action_settings))

  def testShouldSendNotificationInsufficientConfidence(self):
    repo_name = 'repo'
    revision = 'r1'
    url = 'code.review.url'
    commit_position = 1000

    action_settings = {'cr_notification_should_notify_flake_culprit': True}

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = {'minimum_confidence_to_update_cr': 0.5}
    analysis.confidence_in_culprit = 0.4

    culprit = FlakeCulprit.Create(repo_name, revision, commit_position, url)
    culprit.put()
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    self.assertFalse(
        send_notification_for_flake_culprit_pipeline._ShouldSendNotification(
            analysis, action_settings))

  def testShouldSendNotification(self):
    repo_name = 'repo'
    revision = 'r1'
    url = 'code.review.url'
    commit_position = 1000

    action_settings = {'cr_notification_should_notify_flake_culprit': True}

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = {'minimum_confidence_to_update_cr': 0.5}
    analysis.confidence_in_culprit = 0.6

    culprit = FlakeCulprit.Create(repo_name, revision, commit_position, url)
    culprit.put()
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    self.assertTrue(
        send_notification_for_flake_culprit_pipeline._ShouldSendNotification(
            analysis, action_settings))

  @mock.patch.object(codereview_util, 'GetCodeReviewForReview')
  @mock.patch.object(codereview.CodeReview, 'PostMessage')
  def testSendNotificationForCulpritNoCodeReview(self, mocked_post_message,
                                                 mocked_get_code_review):
    mocked_post_message.return_value = False
    mocked_get_code_review.return_value = None
    culprit = FlakeCulprit.Create('repo', 'revision', 12345)
    culprit.put()

    send_notification_for_flake_culprit_pipeline._SendNotificationForCulprit(
        culprit, 'host', 'change_id')
    culprit = ndb.Key(urlsafe=culprit.key.urlsafe()).get()
    self.assertEqual(culprit.cr_notification_status, analysis_status.ERROR)

  @mock.patch.object(codereview_util, 'GetCodeReviewForReview')
  @mock.patch.object(codereview.CodeReview, 'PostMessage')
  def testSendNotificationForCulpritNoChangeId(self, mocked_post_message,
                                               mocked_get_code_review):
    mocked_post_message.return_value = False
    mocked_get_code_review.return_value = None
    culprit = FlakeCulprit.Create('repo', 'revision', 12345)
    culprit.put()

    send_notification_for_flake_culprit_pipeline._SendNotificationForCulprit(
        culprit, 'host', None)
    culprit = ndb.Key(urlsafe=culprit.key.urlsafe()).get()
    self.assertEqual(culprit.cr_notification_status, analysis_status.ERROR)

  @mock.patch.object(codereview_util, 'GetCodeReviewForReview')
  @mock.patch.object(codereview.CodeReview, 'PostMessage')
  def testSendNotificationForCulpritSuccess(self, mocked_post_message, _):
    mocked_post_message.return_value = True
    culprit = FlakeCulprit.Create('repo', 'revision', 12345)
    culprit.put()

    send_notification_for_flake_culprit_pipeline._SendNotificationForCulprit(
        culprit, 'host', 'change_id')
    culprit = ndb.Key(urlsafe=culprit.key.urlsafe()).get()
    self.assertEqual(culprit.cr_notification_status, analysis_status.COMPLETED)

  def testSendNotificationForflakeCulpritPipelineNoCulprit(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.put()
    pipeline_job = SendNotificationForFlakeCulpritPipeline()
    self.assertFalse(pipeline_job.run(analysis.key.urlsafe()))

  @mock.patch.object(
      send_notification_for_flake_culprit_pipeline,
      '_ShouldSendNotification',
      return_value=False)
  def testSendNotificationForflakeCulpritPipelineShouldNotSend(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    culprit = FlakeCulprit.Create('repo', 'revision', 12345)
    culprit.put()
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    pipeline_job = SendNotificationForFlakeCulpritPipeline()
    self.assertFalse(pipeline_job.run(analysis.key.urlsafe()))

  @mock.patch.object(
      send_notification_for_flake_culprit_pipeline,
      '_SendNotificationForCulprit',
      return_value=True)
  @mock.patch.object(suspected_cl_util, 'GetCulpritInfo')
  def testSendNotificationForflakeCulpritPipeline(
      self, mocked_get_culprit_info, _):
    mocked_get_culprit_info.return_value = {
        'review_server_host': 'host',
        'review_change_id': 'change_id'
    }
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = {'minimum_confidence_to_update_cr': 0.5}
    culprit = FlakeCulprit.Create('repo', 'revision', 12345)
    culprit.put()
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.confidence_in_culprit = 1.0
    analysis.put()

    pipeline_job = SendNotificationForFlakeCulpritPipeline()
    self.assertTrue(pipeline_job.run(analysis.key.urlsafe()))
