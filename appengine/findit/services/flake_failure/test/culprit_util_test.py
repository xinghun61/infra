# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
from datetime import datetime

from google.appengine.ext import ndb

from common.waterfall import failure_type
from libs import analysis_status
from libs import time_util
from infra_api_clients.codereview import codereview
from infra_api_clients.codereview import codereview_util
from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.data_point import DataPoint
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure.create_and_submit_revert_pipeline import (
    CreateAndSubmitRevertInput)
from services import constants
from services import culprit_action
from services import gerrit
from services import git
from services.flake_failure import culprit_util
from services.flake_failure import flake_constants
from services.parameters import CreateRevertCLParameters
from services.parameters import SubmitRevertCLParameters
from waterfall import waterfall_config
from waterfall.test import wf_testcase


class CulpritUtilTest(wf_testcase.WaterfallTestCase):

  def testAbortCreateAndSubmitRevertNothingMatchesNothingChanged(self):
    pipeline_id = 'foobar'
    build_key = 'buildid'
    repo = 'chromium'
    rev = 'rev1'
    commit_position = 100
    pipeline_id = 'foo'

    culprit = FlakeCulprit.Create(repo, rev, commit_position)
    culprit.put()

    culprit.put = mock.Mock()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    pipeline_input = CreateAndSubmitRevertInput(
        analysis_urlsafe_key=analysis.key.urlsafe(), build_key=build_key)

    culprit_util.AbortCreateAndSubmitRevert(pipeline_input, pipeline_id)
    culprit.put.assert_not_called()

  def testAbortCreateAndSubmitRevertRevertCreationFails(self):
    pipeline_id = 'foobar'
    build_key = 'buildid'
    repo = 'chromium'
    rev = 'rev1'
    commit_position = 100
    pipeline_id = 'foo'

    culprit = FlakeCulprit.Create(repo, rev, commit_position)
    culprit.revert_pipeline_id = pipeline_id
    culprit.revert_status = analysis_status.SKIPPED
    culprit.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    pipeline_input = CreateAndSubmitRevertInput(
        analysis_urlsafe_key=analysis.key.urlsafe(), build_key=build_key)

    culprit_util.AbortCreateAndSubmitRevert(pipeline_input, pipeline_id)
    self.assertIsNone(culprit.revert_pipeline_id)
    self.assertEqual(analysis_status.ERROR, culprit.revert_status)

  def testAbortCreateAndSubmitRevertRevertSubmissionFails(self):
    pipeline_id = 'foobar'
    build_key = 'buildid'
    repo = 'chromium'
    rev = 'rev1'
    commit_position = 100
    pipeline_id = 'foo'

    culprit = FlakeCulprit.Create(repo, rev, commit_position)
    culprit.submit_revert_pipeline_id = pipeline_id
    culprit.revert_submission_status = analysis_status.SKIPPED
    culprit.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    pipeline_input = CreateAndSubmitRevertInput(
        analysis_urlsafe_key=analysis.key.urlsafe(), build_key=build_key)

    culprit_util.AbortCreateAndSubmitRevert(pipeline_input, pipeline_id)
    self.assertIsNone(culprit.submit_revert_pipeline_id)
    self.assertEqual(analysis_status.ERROR, culprit.revert_submission_status)

  @mock.patch.object(
      culprit_action, 'CommitRevert', return_value=constants.COMMITTED)
  @mock.patch.object(
      culprit_action, 'RevertCulprit', return_value=constants.CREATED_BY_FINDIT)
  @mock.patch.object(culprit_util, 'CanRevertForAnalysis', return_value=True)
  @mock.patch.object(culprit_util, 'UnderLimitForAutorevert', return_value=True)
  def testCreateAndSubmitRevert(self, under_limit, can_revert, revert_fn,
                                commit_fn):
    build_key = 'mock_build_key'
    repo = 'chromium'
    rev = 'rev1'
    commit_position = 100
    pipeline_id = 'foo'

    culprit = FlakeCulprit.Create(repo, rev, commit_position)
    culprit.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    revert_expected = CreateRevertCLParameters(
        cl_key=culprit.key.urlsafe(),
        build_key=build_key,
        failure_type=failure_type.FLAKY_TEST)
    submit_expected = SubmitRevertCLParameters(
        cl_key=culprit.key.urlsafe(),
        revert_status=constants.CREATED_BY_FINDIT,
        failure_type=failure_type.FLAKY_TEST)

    pipeline_input = CreateAndSubmitRevertInput(
        analysis_urlsafe_key=analysis.key.urlsafe(), build_key=build_key)
    culprit_util.CreateAndSubmitRevert(pipeline_input, pipeline_id)

    under_limit.assert_called_once()
    can_revert.assert_called_once_with(analysis)
    revert_fn.assert_called_once_with(revert_expected, pipeline_id)
    commit_fn.assert_called_once_with(submit_expected, pipeline_id)

    self.assertTrue(analysis.has_created_autorevert)
    self.assertTrue(analysis.has_submitted_autorevert)

  @mock.patch.object(
      culprit_action, 'CommitRevert', return_value=constants.COMMITTED)
  @mock.patch.object(
      culprit_action, 'RevertCulprit', return_value=constants.CREATED_BY_FINDIT)
  @mock.patch.object(culprit_util, 'CanRevertForAnalysis', return_value=True)
  @mock.patch.object(
      culprit_util, 'UnderLimitForAutorevert', return_value=False)
  def testCreateAndSubmitRevertOverLimit(self, under_limit, can_revert,
                                         revert_fn, commit_fn):
    build_key = 'mock_build_key'
    repo = 'chromium'
    rev = 'rev1'
    commit_position = 100
    pipeline_id = 'foo'

    culprit = FlakeCulprit.Create(repo, rev, commit_position)
    culprit.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    pipeline_input = CreateAndSubmitRevertInput(
        analysis_urlsafe_key=analysis.key.urlsafe(), build_key=build_key)
    culprit_util.CreateAndSubmitRevert(pipeline_input, pipeline_id)

    under_limit.assert_called_once()
    can_revert.assert_not_called()
    revert_fn.assert_not_called()
    commit_fn.assert_not_called()

    self.assertFalse(analysis.has_created_autorevert)
    self.assertFalse(analysis.has_submitted_autorevert)

  @mock.patch.object(
      culprit_action, 'CommitRevert', return_value=constants.COMMITTED)
  @mock.patch.object(
      culprit_action, 'RevertCulprit', return_value=constants.CREATED_BY_FINDIT)
  @mock.patch.object(culprit_util, 'CanRevertForAnalysis', return_value=False)
  @mock.patch.object(culprit_util, 'UnderLimitForAutorevert', return_value=True)
  def testCreateAndSubmitRevertCannotRevert(self, under_limit, can_revert,
                                            revert_fn, commit_fn):
    build_key = 'mock_build_key'
    repo = 'chromium'
    rev = 'rev1'
    commit_position = 100
    pipeline_id = 'foo'

    culprit = FlakeCulprit.Create(repo, rev, commit_position)
    culprit.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    pipeline_input = CreateAndSubmitRevertInput(
        analysis_urlsafe_key=analysis.key.urlsafe(), build_key=build_key)
    culprit_util.CreateAndSubmitRevert(pipeline_input, pipeline_id)

    under_limit.assert_called_once()
    can_revert.assert_called_once_with(analysis)
    revert_fn.assert_not_called()
    commit_fn.assert_not_called()

    self.assertFalse(analysis.has_created_autorevert)
    self.assertFalse(analysis.has_submitted_autorevert)

  @mock.patch.object(
      culprit_action, 'CommitRevert', return_value=constants.COMMITTED)
  @mock.patch.object(
      culprit_action,
      'RevertCulprit',
      return_value=constants.CREATED_BY_SHERIFF)
  @mock.patch.object(culprit_util, 'CanRevertForAnalysis', return_value=True)
  @mock.patch.object(culprit_util, 'UnderLimitForAutorevert', return_value=True)
  def testCreateAndSubmitRevertCreateFailed(self, under_limit, can_revert,
                                            revert_fn, commit_fn):
    build_key = 'mock_build_key'
    repo = 'chromium'
    rev = 'rev1'
    commit_position = 100
    pipeline_id = 'foo'

    culprit = FlakeCulprit.Create(repo, rev, commit_position)
    culprit.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    revert_expected = CreateRevertCLParameters(
        cl_key=culprit.key.urlsafe(),
        build_key=build_key,
        failure_type=failure_type.FLAKY_TEST)

    pipeline_input = CreateAndSubmitRevertInput(
        analysis_urlsafe_key=analysis.key.urlsafe(), build_key=build_key)
    culprit_util.CreateAndSubmitRevert(pipeline_input, pipeline_id)

    under_limit.assert_called_once()
    can_revert.assert_called_once_with(analysis)
    revert_fn.assert_called_once_with(revert_expected, pipeline_id)
    commit_fn.assert_not_called()

    self.assertFalse(analysis.has_created_autorevert)
    self.assertFalse(analysis.has_submitted_autorevert)

  @mock.patch.object(
      culprit_action, 'CommitRevert', return_value=constants.ERROR)
  @mock.patch.object(
      culprit_action, 'RevertCulprit', return_value=constants.CREATED_BY_FINDIT)
  @mock.patch.object(culprit_util, 'CanRevertForAnalysis', return_value=True)
  @mock.patch.object(culprit_util, 'UnderLimitForAutorevert', return_value=True)
  def testCreateAndSubmitRevertSubmitFailed(self, under_limit, can_revert,
                                            revert_fn, commit_fn):
    build_key = 'mock_build_key'
    repo = 'chromium'
    rev = 'rev1'
    commit_position = 100
    pipeline_id = 'foo'

    culprit = FlakeCulprit.Create(repo, rev, commit_position)
    culprit.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    revert_expected = CreateRevertCLParameters(
        cl_key=culprit.key.urlsafe(),
        build_key=build_key,
        failure_type=failure_type.FLAKY_TEST)
    submit_expected = SubmitRevertCLParameters(
        cl_key=culprit.key.urlsafe(),
        revert_status=constants.CREATED_BY_FINDIT,
        failure_type=failure_type.FLAKY_TEST)

    pipeline_input = CreateAndSubmitRevertInput(
        analysis_urlsafe_key=analysis.key.urlsafe(), build_key=build_key)
    culprit_util.CreateAndSubmitRevert(pipeline_input, pipeline_id)

    under_limit.assert_called_once()
    can_revert.assert_called_once_with(analysis)
    revert_fn.assert_called_once_with(revert_expected, pipeline_id)
    commit_fn.assert_called_once_with(submit_expected, pipeline_id)

    self.assertTrue(analysis.has_created_autorevert)
    self.assertFalse(analysis.has_submitted_autorevert)
    self.assertIsNone(analysis.autorevert_submission_time)

  @mock.patch.object(
      time_util, 'GetMostRecentUTCMidnight', return_value=datetime(2018, 1, 1))
  def testUnderLimitForAutoRevert(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.Update(
        autorevert_submission_time=datetime(2018, 1, 1, 1),
        has_submitted_autorevert=True)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.Update(
        autorevert_submission_time=datetime(2018, 1, 1, 1),
        has_submitted_autorevert=True)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.Update(
        autorevert_submission_time=datetime(2018, 1, 1, 1),
        has_submitted_autorevert=True)

    self.assertTrue(culprit_util.UnderLimitForAutorevert())

    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.Update(
        autorevert_submission_time=datetime(2018, 1, 1, 1),
        has_submitted_autorevert=True)

    self.assertFalse(culprit_util.UnderLimitForAutorevert())

  @mock.patch.object(git, 'ChangeCommittedWithinTime', return_value=True)
  def testCanRevertForAnalysis(self, mock_time_fn):
    culprit = FlakeCulprit.Create('chromium', 'r13', 100)
    culprit.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=99, pass_rate=-1.0)
    ]
    analysis.Update(
        confidence_in_culprit=1.0, culprit_urlsafe_key=culprit.key.urlsafe())
    self.assertTrue(culprit_util.CanRevertForAnalysis(analysis))
    mock_time_fn.assert_called_with('r13')

  def testCanRevertForAnalysisInsufficientConfidenceReturnsFalse(self):
    culprit = FlakeCulprit.Create('chromium', 'r13', 100)
    culprit.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=99, pass_rate=-1.0)
    ]
    analysis.Update(
        confidence_in_culprit=0.1, culprit_urlsafe_key=culprit.key.urlsafe())

    self.assertFalse(culprit_util.CanRevertForAnalysis(analysis))

  def testCanRevertForAnalysisNotNewlyAddedTest(self):
    culprit = FlakeCulprit.Create('chromium', 'r13', 100)
    culprit.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.data_points = [DataPoint.Create(commit_position=99, pass_rate=1.0)]
    analysis.Update(
        confidence_in_culprit=1.0, culprit_urlsafe_key=culprit.key.urlsafe())

    self.assertFalse(culprit_util.CanRevertForAnalysis(analysis))

  @mock.patch.object(git, 'ChangeCommittedWithinTime', return_value=False)
  def testCanRevertForAnalysisCulpritTooOld(self, mock_time_fn):
    culprit = FlakeCulprit.Create('chromium', 'r13', 100)
    culprit.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 100, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=99, pass_rate=-1.0)
    ]
    analysis.Update(
        confidence_in_culprit=1.0, culprit_urlsafe_key=culprit.key.urlsafe())

    self.assertFalse(culprit_util.CanRevertForAnalysis(analysis))
    mock_time_fn.assert_called_with('r13')

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

  def testIsConfiguredToNotifyCulpritsFalse(self):
    self.UpdateUnitTestConfigSettings(
        'action_settings',
        {'cr_notification_should_notify_flake_culprit': False})
    self.assertFalse(culprit_util.IsConfiguredToNotifyCulprits())

  def testIsConfiguredToNotifyCulpritsTrue(self):
    self.UpdateUnitTestConfigSettings(
        'action_settings',
        {'cr_notification_should_notify_flake_culprit': True})
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
      culprit_util, 'GetMinimumConfidenceToNotifyCulprits', return_value=0.5)
  def testShouldSendNotification(self, *_):
    repo_name = 'repo'
    revision = 'r1'
    url = 'code.review.url'
    commit_position = 1000

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
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
  @mock.patch.object(git, 'GetCodeReviewInfoForACommit')
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

    self.assertFalse(culprit_util.NotifyCulprit(culprit, None))
    culprit = ndb.Key(urlsafe=culprit.key.urlsafe()).get()
    self.assertEqual(culprit.cr_notification_status, analysis_status.ERROR)

  @mock.patch.object(codereview_util, 'GetCodeReviewForReview')
  @mock.patch.object(codereview.CodeReview, 'PostMessage')
  @mock.patch.object(git, 'GetCodeReviewInfoForACommit')
  def testSendNotificationForCulpritNoChangeId(
      self, mocked_culprit_info, mocked_post_message, mocked_get_code_review):
    mocked_culprit_info.return_value = {
        'review_server_host': 'host',
    }
    mocked_post_message.return_value = False
    mocked_get_code_review.return_value = None
    culprit = FlakeCulprit.Create('repo', 'revision', 12345)
    culprit.put()

    self.assertFalse(culprit_util.NotifyCulprit(culprit, None))
    culprit = ndb.Key(urlsafe=culprit.key.urlsafe()).get()
    self.assertEqual(culprit.cr_notification_status, analysis_status.ERROR)

  @mock.patch.object(codereview_util, 'GetCodeReviewForReview')
  @mock.patch.object(codereview.CodeReview, 'PostMessage')
  @mock.patch.object(git, 'GetCodeReviewInfoForACommit')
  def testSendNotificationForCulpritSuccess(self, mocked_culprit_info,
                                            mocked_post_message, _):
    mocked_culprit_info.return_value = {
        'review_server_host': 'host',
        'review_change_id': 'change_id'
    }
    mocked_post_message.return_value = True
    culprit = FlakeCulprit.Create('repo', 'revision', 12345)
    culprit.put()

    self.assertTrue(culprit_util.NotifyCulprit(culprit, None))
    culprit = ndb.Key(urlsafe=culprit.key.urlsafe()).get()
    self.assertEqual(culprit.cr_notification_status, analysis_status.COMPLETED)

  @mock.patch.object(codereview_util, 'GetCodeReviewForReview')
  @mock.patch.object(codereview.CodeReview, 'PostMessage')
  @mock.patch.object(git, 'GetCodeReviewInfoForACommit')
  def testSendNotificationForCulprit(self, mocked_culprit_info,
                                     mocked_post_message, _):
    mocked_culprit_info.return_value = {
        'review_server_host': 'host',
        'review_change_id': 'change_id'
    }
    mocked_post_message.return_value = True
    culprit = FlakeCulprit.Create('repo', 'revision', 12345)
    culprit.put()

    self.assertTrue(culprit_util.NotifyCulprit(culprit, None))
    culprit = ndb.Key(urlsafe=culprit.key.urlsafe()).get()
    self.assertEqual(culprit.cr_notification_status, analysis_status.COMPLETED)

  def testGenerateMessageTextWithBug(self):
    bug_id = 98765
    culprit = FlakeCulprit.Create('repo', 'revision', 12345)
    self.assertIn(
        str(bug_id), culprit_util._GenerateMessageText(culprit, bug_id))

  def testGenerateMessageTextWithoutBug(self):
    culprit = FlakeCulprit.Create('repo', 'revision', 12345)
    self.assertIn('revision', culprit_util._GenerateMessageText(culprit, None))
