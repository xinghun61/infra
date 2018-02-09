# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from google.appengine.ext import ndb

from libs import analysis_status
from infra_api_clients.codereview import codereview
from infra_api_clients.codereview import codereview_util
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from services.flake_failure import culprit_util
from waterfall import suspected_cl_util
from waterfall.flake import flake_constants
from waterfall.test import wf_testcase


class DataPointUtilTest(wf_testcase.WaterfallTestCase):

  def testNewlyAddedTest(self):
    culprit_commit_position = 11
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=flake_constants.PASS_RATE_TEST_NOT_FOUND,
            commit_position=culprit_commit_position - 1),
        DataPoint.Create(
            pass_rate=0.5, commit_position=culprit_commit_position),
    ]
    self.assertTrue(
        culprit_util.CulpritAddedNewFlakyTest(analysis,
                                              culprit_commit_position))

  def testGetMinimumConfidenceToNotifyCulprits(self):
    self.assertEqual(
        flake_constants.DEFAULT_MINIMUM_CONFIDENCE_SCORE_TO_UPDATE_CR,
        culprit_util.GetMinimumConfidenceToNotifyCulprits())

  def testHasSeriesOfFullyStablePointsPrecedingCulprit(self):
    culprit_commit_position = 13
    culprit = FlakeCulprit.Create('chromium', 'r13', culprit_commit_position)
    culprit.put()
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(pass_rate=0.0, commit_position=10),
        DataPoint.Create(pass_rate=0.0, commit_position=11),
        DataPoint.Create(pass_rate=0.0, commit_position=12),
        DataPoint.Create(
            pass_rate=0.4, commit_position=culprit_commit_position),
    ]
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    self.assertTrue(
        culprit_util.HasSeriesOfFullyStablePointsPrecedingCulprit(analysis))

  def testIsConfiguredToNotifyCulpritsFalse(self):
    self.UpdateUnitTestConfigSettings('action_settings', {
        'cr_notification_should_notify_flake_culprit': False
    })
    self.assertFalse(culprit_util.IsConfiguredToNotifyCulprits())

  def testIsConfiguredToNotifyCulpritsTrue(self):
    self.UpdateUnitTestConfigSettings('action_settings', {
        'cr_notification_should_notify_flake_culprit': True
    })
    self.assertTrue(culprit_util.IsConfiguredToNotifyCulprits())

  def testPrepareCulpritForSendingNotificationAlreadySent(self):
    repo_name = 'repo'
    revision = 'r1'
    url = 'code.review.url'
    commit_position = 1000

    culprit = FlakeCulprit.Create(repo_name, revision, commit_position, url)
    culprit.cr_notification_status = analysis_status.COMPLETED
    culprit.put()

    self.assertFalse(
        culprit_util.PrepareCulpritForSendingNotification(
            culprit.key.urlsafe()))

  def testPrepareCulpritForSendingNotificationAlreadyRunning(self):
    repo_name = 'repo'
    revision = 'r1'
    url = 'code.review.url'
    commit_position = 1000

    culprit = FlakeCulprit.Create(repo_name, revision, commit_position, url)
    culprit.cr_notification_status = analysis_status.RUNNING
    culprit.put()

    self.assertFalse(
        culprit_util.PrepareCulpritForSendingNotification(
            culprit.key.urlsafe()))

  def testPrepareCulpritForSendingNotification(self):
    repo_name = 'repo'
    revision = 'r1'
    url = 'code.review.url'
    commit_position = 1000

    culprit = FlakeCulprit.Create(repo_name, revision, commit_position, url)
    culprit.put()

    self.assertTrue(
        culprit_util.PrepareCulpritForSendingNotification(
            culprit.key.urlsafe()))

    culprit = ndb.Key(urlsafe=culprit.key.urlsafe()).get()
    self.assertEqual(analysis_status.RUNNING, culprit.cr_notification_status)

  @mock.patch.object(
      culprit_util, 'IsConfiguredToNotifyCulprits', return_value=False)
  def testShouldSendNotificationConfigSetFalse(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    self.assertFalse(culprit_util.ShouldNotifyCulprit(analysis))

  @mock.patch.object(
      culprit_util, 'IsConfiguredToNotifyCulprits', return_value=True)
  def testShouldSendNotificationAlreadyProcessed(self, _):
    repo_name = 'repo'
    revision = 'r1'
    url = 'code.review.url'
    commit_position = 1000

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')

    culprit = FlakeCulprit.Create(repo_name, revision, commit_position, url)
    culprit.cr_notification_status = analysis_status.COMPLETED
    culprit.put()
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    self.assertFalse(culprit_util.ShouldNotifyCulprit(analysis))

  @mock.patch.object(
      culprit_util, 'IsConfiguredToNotifyCulprits', return_value=True)
  @mock.patch.object(
      culprit_util, 'CulpritAddedNewFlakyTest', return_value=True)
  def testShouldSendNotificationNewlyAddedTest(self, *_):
    repo_name = 'repo'
    revision = 'r1'
    url = 'code.review.url'
    commit_position = 1000

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

    self.assertTrue(culprit_util.ShouldNotifyCulprit(analysis))

  @mock.patch.object(
      culprit_util, 'IsConfiguredToNotifyCulprits', return_value=True)
  @mock.patch.object(
      culprit_util, 'CulpritAddedNewFlakyTest', return_value=False)
  @mock.patch.object(
      culprit_util,
      'HasSeriesOfFullyStablePointsPrecedingCulprit',
      return_value=False)
  def testShouldSendNotificationInsufficientTrulyStableDataPoints(self, *_):
    repo_name = 'repo'
    revision = 'r1'
    url = 'code.review.url'
    commit_position = 1000

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

    self.assertFalse(culprit_util.ShouldNotifyCulprit(analysis))

  @mock.patch.object(
      culprit_util, 'IsConfiguredToNotifyCulprits', return_value=True)
  @mock.patch.object(
      culprit_util, 'CulpritAddedNewFlakyTest', return_value=False)
  @mock.patch.object(
      culprit_util,
      'HasSeriesOfFullyStablePointsPrecedingCulprit',
      return_value=True)
  @mock.patch.object(
      culprit_util, 'GetMinimumConfidenceToNotifyCulprits', return_value=1.0)
  def testShouldSendNotificationInsufficientConfidence(self, *_):
    repo_name = 'repo'
    revision = 'r1'
    url = 'code.review.url'
    commit_position = 1000

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.confidence_in_culprit = 0.4

    culprit = FlakeCulprit.Create(repo_name, revision, commit_position, url)
    culprit.put()
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.data_points = [
        DataPoint.Create(pass_rate=1.0, commit_position=commit_position - 1),
        DataPoint.Create(pass_rate=0.4, commit_position=commit_position),
    ]
    analysis.confidence_in_culprit = 0.0
    analysis.put()

    self.assertFalse(culprit_util.ShouldNotifyCulprit(analysis))

  @mock.patch.object(
      culprit_util, 'IsConfiguredToNotifyCulprits', return_value=True)
  @mock.patch.object(
      culprit_util, 'CulpritAddedNewFlakyTest', return_value=False)
  @mock.patch.object(
      culprit_util,
      'HasSeriesOfFullyStablePointsPrecedingCulprit',
      return_value=True)
  @mock.patch.object(
      culprit_util, 'GetMinimumConfidenceToNotifyCulprits', return_value=0.5)
  def testShouldSendNotification(self, *_):
    repo_name = 'repo'
    revision = 'r1'
    url = 'code.review.url'
    commit_position = 1000

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
    analysis.confidence_in_culprit = 0.6
    analysis.put()

    self.assertTrue(culprit_util.ShouldNotifyCulprit(analysis))

  @mock.patch.object(codereview_util, 'GetCodeReviewForReview')
  @mock.patch.object(codereview.CodeReview, 'PostMessage')
  @mock.patch.object(suspected_cl_util, 'GetCulpritInfo')
  def testNotifyCulpritNoCodeReview(
      self, mocked_culprit_info, mocked_post_message, mocked_get_code_review):
    mocked_culprit_info.return_value = {
        'review_server_host': 'host',
        'review_change_id': 'change_id'
    }
    mocked_post_message.return_value = False
    mocked_get_code_review.return_value = None
    culprit = FlakeCulprit.Create('repo', 'revision', 12345)
    culprit.put()

    self.assertFalse(culprit_util.NotifyCulprit(culprit))
    culprit = ndb.Key(urlsafe=culprit.key.urlsafe()).get()
    self.assertEqual(culprit.cr_notification_status, analysis_status.ERROR)

  @mock.patch.object(codereview_util, 'GetCodeReviewForReview')
  @mock.patch.object(codereview.CodeReview, 'PostMessage')
  @mock.patch.object(suspected_cl_util, 'GetCulpritInfo')
  def testSendNotificationForCulpritNoChangeId(
      self, mocked_culprit_info, mocked_post_message, mocked_get_code_review):
    mocked_culprit_info.return_value = {
        'review_server_host': 'host',
    }
    mocked_post_message.return_value = False
    mocked_get_code_review.return_value = None
    culprit = FlakeCulprit.Create('repo', 'revision', 12345)
    culprit.put()

    self.assertFalse(culprit_util.NotifyCulprit(culprit))
    culprit = ndb.Key(urlsafe=culprit.key.urlsafe()).get()
    self.assertEqual(culprit.cr_notification_status, analysis_status.ERROR)

  @mock.patch.object(codereview_util, 'GetCodeReviewForReview')
  @mock.patch.object(codereview.CodeReview, 'PostMessage')
  @mock.patch.object(suspected_cl_util, 'GetCulpritInfo')
  def testSendNotificationForCulpritSuccess(self, mocked_culprit_info,
                                            mocked_post_message, _):
    mocked_culprit_info.return_value = {
        'review_server_host': 'host',
        'review_change_id': 'change_id'
    }
    mocked_post_message.return_value = True
    culprit = FlakeCulprit.Create('repo', 'revision', 12345)
    culprit.put()

    self.assertTrue(culprit_util.NotifyCulprit(culprit))
    culprit = ndb.Key(urlsafe=culprit.key.urlsafe()).get()
    self.assertEqual(culprit.cr_notification_status, analysis_status.COMPLETED)
