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
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import suspected_cl_util
from waterfall.flake import flake_constants
from waterfall.flake import send_notification_for_flake_culprit_pipeline
from waterfall.flake.send_notification_for_flake_culprit_pipeline import (
    _HasSeriesOfFullyStablePointsPrecedingCommitPosition)
from waterfall.flake.send_notification_for_flake_culprit_pipeline import (
    _HasSeriesOfFullyStablePointsPrecedingCulprit)
from waterfall.flake.send_notification_for_flake_culprit_pipeline import (
    SendNotificationForFlakeCulpritPipeline)

from waterfall.test import wf_testcase


class SendNotificationForFlakeCulpritPipelineTest(
    wf_testcase.WaterfallTestCase):

  app_module = pipeline_handlers._APP

  def testNewlyAddedTestPositiveCase(self):
    culprit_commit_position = 11
    culprit = FlakeCulprit.Create('chromium', 'r11', culprit_commit_position)
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=flake_constants.PASS_RATE_TEST_NOT_FOUND,
            commit_position=culprit_commit_position - 1),
        DataPoint.Create(
            pass_rate=0.5, commit_position=culprit_commit_position),
    ]
    self.assertTrue(
        send_notification_for_flake_culprit_pipeline._NewlyAddedTest(
            analysis, culprit))

  def testNewlyAddedTestNegativeCase(self):
    culprit_commit_position = 11
    culprit = FlakeCulprit.Create('chromium', 'r11', culprit_commit_position)
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=1.0, commit_position=culprit_commit_position - 1),
        DataPoint.Create(
            pass_rate=0.5, commit_position=culprit_commit_position),
    ]
    self.assertFalse(
        send_notification_for_flake_culprit_pipeline._NewlyAddedTest(
            analysis, culprit))

  def testNewlyAddedTestCulpritNotFound(self):
    culprit_commit_position = 12
    culprit = FlakeCulprit.Create('chromium', 'r11', culprit_commit_position)
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=1.0, commit_position=culprit_commit_position - 2),
        DataPoint.Create(
            pass_rate=1.0, commit_position=culprit_commit_position - 1),
    ]
    self.assertFalse(
        send_notification_for_flake_culprit_pipeline._NewlyAddedTest(
            analysis, culprit))

  def testHasSeriesOfFullyStablePointsPrecedingCommitPosition(self):
    self.assertFalse(  # Not enough data points.
        _HasSeriesOfFullyStablePointsPrecedingCommitPosition([], 100, 1))
    self.assertFalse(  # Not enough data points in a row.
        _HasSeriesOfFullyStablePointsPrecedingCommitPosition([
            DataPoint.Create(pass_rate=1.0, commit_position=10),
            DataPoint.Create(pass_rate=1.0, commit_position=11),
            DataPoint.Create(pass_rate=0.4, commit_position=12),
        ], 12, 3))
    self.assertFalse(  # Not all data points fully stable.
        _HasSeriesOfFullyStablePointsPrecedingCommitPosition([
            DataPoint.Create(pass_rate=1.0, commit_position=10),
            DataPoint.Create(pass_rate=0.99, commit_position=11),
            DataPoint.Create(pass_rate=1.0, commit_position=12),
            DataPoint.Create(pass_rate=0.4, commit_position=13),
        ], 13, 3))
    self.assertFalse(  # Preceding data points must be of the same stable type.
        _HasSeriesOfFullyStablePointsPrecedingCommitPosition([
            DataPoint.Create(pass_rate=1.0, commit_position=10),
            DataPoint.Create(pass_rate=0.0, commit_position=11),
            DataPoint.Create(pass_rate=1.0, commit_position=12),
            DataPoint.Create(pass_rate=0.4, commit_position=13),
        ], 13, 3))
    self.assertTrue(  # All stable passing.
        _HasSeriesOfFullyStablePointsPrecedingCommitPosition([
            DataPoint.Create(pass_rate=1.0, commit_position=10),
            DataPoint.Create(pass_rate=1.0, commit_position=11),
            DataPoint.Create(pass_rate=1.0, commit_position=12),
            DataPoint.Create(pass_rate=0.4, commit_position=13),
        ], 13, 3))
    self.assertTrue(  # All stable failing.
        _HasSeriesOfFullyStablePointsPrecedingCommitPosition([
            DataPoint.Create(pass_rate=0.0, commit_position=10),
            DataPoint.Create(pass_rate=0.0, commit_position=11),
            DataPoint.Create(pass_rate=0.0, commit_position=12),
            DataPoint.Create(pass_rate=0.4, commit_position=13),
        ], 13, 3))
    self.assertTrue(  # Stable failing, stable passing, stable failing.
        _HasSeriesOfFullyStablePointsPrecedingCommitPosition([
            DataPoint.Create(pass_rate=0.0, commit_position=10),
            DataPoint.Create(pass_rate=1.0, commit_position=11),
            DataPoint.Create(pass_rate=0.0, commit_position=12),
            DataPoint.Create(pass_rate=0.0, commit_position=13),
            DataPoint.Create(pass_rate=0.0, commit_position=14),
            DataPoint.Create(pass_rate=0.0, commit_position=15),
        ], 15, 3))
    self.assertTrue(
        _HasSeriesOfFullyStablePointsPrecedingCommitPosition([
            DataPoint.Create(pass_rate=0.0, commit_position=10),
            DataPoint.Create(pass_rate=0.0, commit_position=11),
            DataPoint.Create(pass_rate=0.0, commit_position=12),
        ], 13, 3))

  def testHasSeriesOfFullyStablePointsPrecedingCulprit(self):
    culprit_commit_position = 13
    culprit = FlakeCulprit.Create('chromium', 'r13', culprit_commit_position)
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(pass_rate=0.0, commit_position=10),
        DataPoint.Create(pass_rate=0.0, commit_position=11),
        DataPoint.Create(pass_rate=0.0, commit_position=12),
        DataPoint.Create(
            pass_rate=0.4, commit_position=culprit_commit_position),
    ]
    self.assertTrue(
        _HasSeriesOfFullyStablePointsPrecedingCulprit(analysis, culprit))

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

  @mock.patch.object(
      send_notification_for_flake_culprit_pipeline,
      '_NewlyAddedTest',
      return_value=True)
  def testShouldSendNotificationNewlyAddedTest(self, _):
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
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=flake_constants.PASS_RATE_TEST_NOT_FOUND,
            commit_position=commit_position - 1),
        DataPoint.Create(pass_rate=0.4, commit_position=commit_position),
    ]
    analysis.put()

    self.assertTrue(
        send_notification_for_flake_culprit_pipeline._ShouldSendNotification(
            analysis, action_settings))

  @mock.patch.object(
      send_notification_for_flake_culprit_pipeline,
      '_NewlyAddedTest',
      return_value=False)
  @mock.patch.object(
      send_notification_for_flake_culprit_pipeline,
      '_HasSeriesOfFullyStablePointsPrecedingCulprit',
      return_value=False)
  def testShouldSendNotificationInsufficientTrulyStableDataPoints(self, *_):
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
    analysis.data_points = [
        DataPoint.Create(pass_rate=1.0, commit_position=commit_position - 1),
        DataPoint.Create(pass_rate=0.4, commit_position=commit_position),
    ]
    analysis.put()

    self.assertFalse(
        send_notification_for_flake_culprit_pipeline._ShouldSendNotification(
            analysis, action_settings))

  @mock.patch.object(
      send_notification_for_flake_culprit_pipeline,
      '_NewlyAddedTest',
      return_value=False)
  @mock.patch.object(
      send_notification_for_flake_culprit_pipeline,
      '_HasSeriesOfFullyStablePointsPrecedingCulprit',
      return_value=True)
  def testShouldSendNotificationInsufficientConfidence(self, *_):
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
    analysis.data_points = [
        DataPoint.Create(pass_rate=1.0, commit_position=commit_position - 1),
        DataPoint.Create(pass_rate=0.4, commit_position=commit_position),
    ]
    analysis.put()

    self.assertFalse(
        send_notification_for_flake_culprit_pipeline._ShouldSendNotification(
            analysis, action_settings))

  @mock.patch.object(
      send_notification_for_flake_culprit_pipeline,
      '_NewlyAddedTest',
      return_value=False)
  @mock.patch.object(
      send_notification_for_flake_culprit_pipeline,
      '_HasSeriesOfFullyStablePointsPrecedingCulprit',
      return_value=True)
  def testShouldSendNotification(self, *_):
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
    analysis.data_points = [
        DataPoint.Create(pass_rate=1.0, commit_position=commit_position - 1),
        DataPoint.Create(pass_rate=0.4, commit_position=commit_position),
    ]
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
  @mock.patch.object(
      send_notification_for_flake_culprit_pipeline,
      '_ShouldSendNotification',
      return_value=True)
  @mock.patch.object(suspected_cl_util, 'GetCulpritInfo')
  def testSendNotificationForflakeCulpritPipeline(self, mocked_get_culprit_info,
                                                  *_):
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
