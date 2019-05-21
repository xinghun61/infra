# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock
import textwrap
import urllib

from common import constants
from common import rotations
from common.waterfall import failure_type
from infra_api_clients.codereview import codereview_util
from infra_api_clients.codereview.cl_info import ClInfo
from infra_api_clients.codereview.cl_info import Commit
from infra_api_clients.codereview.cl_info import PatchSet
from infra_api_clients.codereview.cl_info import Revert
from infra_api_clients.codereview.gerrit import Gerrit
from libs import analysis_status as status
from libs import time_util
from model.base_suspected_cl import RevertCL
from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from model.wf_suspected_cl import WfSuspectedCL
from services import constants as services_constants
from services import gerrit
from services.parameters import SendNotificationForCulpritParameters
from services.parameters import SubmitRevertCLParameters
from waterfall import buildbot
from waterfall import waterfall_config
from waterfall.test import wf_testcase

_CODEREVIEW = Gerrit('chromium-review.googlesource.com')

# pylint:disable=unused-argument, unused-variable
# https://crbug.com/947753


class GerritTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(GerritTest, self).setUp()
    self.culprit_commit_position = 123
    self.culprit_code_review_url = (
        'https://chromium-review.googlesource.com/12345')
    self.review_server_host = 'chromium-review.googlesource.com'
    self.review_change_id = '12345'

    self.codereview_info = {
        'commit_position': self.culprit_commit_position,
        'review_change_id': self.review_change_id,
        'review_server_host': self.review_server_host,
        'author': {
            'email': 'author@abc.com'
        },
        'committer': {
            'time': '2018-07-01 00:00:00'
        },
    }

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=_CODEREVIEW)
  @mock.patch.object(waterfall_config, 'GetActionSettings', return_value={})
  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 2, 1, 16, 0, 0))
  @mock.patch.object(_CODEREVIEW, 'PostMessage', return_value=True)
  @mock.patch.object(rotations, 'current_sheriffs', return_value=['a@b.com'])
  @mock.patch.object(_CODEREVIEW, 'AddReviewers', return_value=True)
  @mock.patch.object(_CODEREVIEW, 'CreateRevert')
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testRevertCLSucceed(self, mock_fn, mock_gerrit, mock_add, *_):
    repo_name = 'chromium'
    revision = 'rev1'
    commit_position = 123
    sample_failed_step = 'compile'

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.commits.append(
        Commit('20001', 'rev1', [], datetime(2017, 2, 1, 0, 0, 0)))
    cl_info.owner_email = 'abc@chromium.org'
    mock_fn.return_value = cl_info
    mock_gerrit.return_value = '54321'

    culprit = WfSuspectedCL.Create(repo_name, revision, commit_position)
    culprit.builds = {
        'm/b/2': {
            'status': None
        },
        'm/b/1': {
            'status': None
        },
        'm/b/3': {
            'status': None
        },
        'm1/b/0': {
            'status': None
        },
    }
    culprit.put()

    revert_status, _, _ = gerrit.RevertCulprit(
        culprit.key.urlsafe(), 'm/b/1', failure_type.COMPILE,
        sample_failed_step, self.codereview_info)

    self.assertEquals(revert_status, services_constants.CREATED_BY_FINDIT)

    reason = textwrap.dedent("""
        Findit (https://goo.gl/kROfz5) identified CL at revision %s as the
        culprit for failures in the build cycles as shown on:
        https://analysis.chromium.org/waterfall/culprit?key=%s\n
        Sample Failed Build: %s\n
        Sample Failed Step: %s""") % (commit_position, culprit.key.urlsafe(),
                                      buildbot.CreateBuildUrl('m', 'b', '1'),
                                      sample_failed_step)
    mock_gerrit.assert_called_once_with(
        reason, self.review_change_id, '20001', bug_id=None)

    culprit_link = ('https://analysis.chromium.org/waterfall/culprit?key=%s' %
                    (culprit.key.urlsafe()))
    false_positive_bug_link = gerrit.CreateFinditWrongBugLink(
        gerrit.FINDIT_BUILD_FAILURE_COMPONENT, culprit_link, revision)

    auto_revert_bug_query = urllib.urlencode({
        'status': 'Available',
        'components': 'Tools>Test>FindIt>Autorevert',
        'summary': 'Auto Revert failed on %s' % revision,
        'comment': 'Detail is %s' % culprit_link
    })
    auto_revert_bug_link = (
        'https://bugs.chromium.org/p/chromium/issues/entry?%s') % (
            auto_revert_bug_query)
    message = textwrap.dedent("""
        Sheriffs, CL owner or CL reviewers:
        Please submit this revert if it is correct.
        If it is a false positive, please abandon and report it
        at %s.
        If failed to submit the revert, please abandon it and report the failure
        at %s.

        For more information about Findit auto-revert: %s.

        Sheriffs, it'll be much appreciated if you could take a couple minutes
        to fill out this survey: %s.""") % (
        false_positive_bug_link, auto_revert_bug_link, gerrit._MANUAL_LINK,
        gerrit._SURVEY_LINK)
    mock_add.assert_called_once_with('54321', ['a@b.com'], message)

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=_CODEREVIEW)
  @mock.patch.object(waterfall_config, 'GetActionSettings', return_value={})
  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 2, 1, 16, 0, 0))
  @mock.patch.object(_CODEREVIEW, 'PostMessage', return_value=True)
  @mock.patch.object(rotations, 'current_sheriffs', return_value=['a@b.com'])
  @mock.patch.object(_CODEREVIEW, 'AddReviewers', return_value=True)
  @mock.patch.object(_CODEREVIEW, 'CreateRevert')
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testRevertCLSucceedFlake(self, mock_fn, mock_gerrit, mock_add, *_):
    repo_name = 'chromium'
    revision = 'rev1'
    commit_position = 123

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.commits.append(
        Commit('20001', 'rev1', [], datetime(2017, 2, 1, 0, 0, 0)))
    cl_info.owner_email = 'abc@chromium.org'
    mock_fn.return_value = cl_info
    mock_gerrit.return_value = '54321'

    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    sample_failed_step = step_name
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.original_master_name = master_name
    analysis.original_builder_name = builder_name
    analysis.original_build_number = build_number
    analysis.original_step_name = step_name
    analysis.original_test_name = test_name
    analysis.bug_id = 1
    analysis.put()

    culprit = FlakeCulprit.Create(repo_name, revision, commit_position)
    culprit.flake_analysis_urlsafe_keys = [analysis.key.urlsafe()]
    culprit.put()

    revert_status, revert, reason = gerrit.RevertCulprit(
        culprit.key.urlsafe(), 'm/b/1', failure_type.FLAKY_TEST,
        sample_failed_step, self.codereview_info)

    self.assertEquals(revert_status, services_constants.CREATED_BY_FINDIT)
    self.assertIsNotNone(revert)
    self.assertIsNone(reason)

    reason = textwrap.dedent("""
      Findit (https://goo.gl/kROfz5) identified CL at revision %s as the
      culprit for flakes in the build cycles as shown on:
      https://analysis.chromium.org/p/chromium/flake-portal/analysis/culprit?key=%s\n
      Sample Failed Build: %s\n
      Sample Failed Step: %s\n
      Sample Flaky Test: %s""") % (
        commit_position or revision, culprit.key.urlsafe(),
        buildbot.CreateBuildUrl('m', 'b', '1'), sample_failed_step, test_name)
    mock_gerrit.assert_called_once_with(
        reason, self.review_change_id, '20001', bug_id=1)

    culprit_link = ('https://analysis.chromium.org/p/chromium/flake-portal/'
                    'analysis/culprit?key=%s' % (culprit.key.urlsafe()))
    false_positive_bug_link = gerrit.CreateFinditWrongBugLink(
        gerrit.FINDIT_BUILD_FAILURE_COMPONENT, culprit_link, revision)

    auto_revert_bug_query = urllib.urlencode({
        'status': 'Available',
        'components': 'Tools>Test>FindIt>Autorevert',
        'summary': 'Auto Revert failed on %s' % revision,
        'comment': 'Detail is %s' % culprit_link
    })
    auto_revert_bug_link = (
        'https://bugs.chromium.org/p/chromium/issues/entry?%s') % (
            auto_revert_bug_query)
    message = textwrap.dedent("""
        Sheriffs, CL owner or CL reviewers:
        Please submit this revert if it is correct.
        If it is a false positive, please abandon and report it
        at %s.
        If failed to submit the revert, please abandon it and report the failure
        at %s.

        For more information about Findit auto-revert: %s.

        Sheriffs, it'll be much appreciated if you could take a couple minutes
        to fill out this survey: %s.""") % (
        false_positive_bug_link, auto_revert_bug_link, gerrit._MANUAL_LINK,
        gerrit._SURVEY_LINK)
    mock_add.assert_called_once_with('54321', ['a@b.com'], message)

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testSheriffRevertedIt(self, mock_fn, _):
    repo_name = 'chromium'
    revision = 'rev1'

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.commits.append(
        Commit('20001', 'rev1', [], datetime(2017, 2, 1, 0, 0, 0)))
    cl_info.owner_email = 'abc@chromium.org'
    revert_cl = ClInfo('revert_review_host', '123V3137')
    cl_info.reverts.append(
        Revert('20001', revert_cl, 'a@b', datetime(2017, 2, 1, 1, 0, 0)))
    mock_fn.return_value = cl_info

    suspect_cl = WfSuspectedCL.Create(repo_name, revision, 123)
    suspect_cl.put()

    revert_status, revert, reason = gerrit.RevertCulprit(
        suspect_cl.key.urlsafe(), 'm/b/1', failure_type.COMPILE, 'compile',
        self.codereview_info)
    self.assertIsNone(revert)
    self.assertEqual(services_constants.REVERTED_BY_SHERIFF, reason)
    self.assertEquals(revert_status, services_constants.CREATED_BY_SHERIFF)

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'AddReviewers', return_value=True)
  @mock.patch.object(rotations, 'current_sheriffs', return_value=['a@b.com'])
  @mock.patch.object(_CODEREVIEW, 'PostMessage')
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testAddedReviewerFailedBefore(self, mock_fn, mock_send, *_):
    repo_name = 'chromium'
    revision = 'rev1'

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.commits.append(
        Commit('20001', 'rev1', [], datetime(2017, 2, 1, 0, 0, 0)))
    cl_info.owner_email = 'abc@chromium.org'
    revert_cl = ClInfo('revert_review_host', '123V3127')
    revert_cl.url = 'https://chromium-review.googlesource.com/54321'
    cl_info.reverts.append(
        Revert('20001', revert_cl, constants.DEFAULT_SERVICE_ACCOUNT,
               datetime(2017, 2, 1, 1, 0, 0)))
    mock_fn.return_value = cl_info

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_cl = RevertCL()
    culprit.revert_status = status.RUNNING
    culprit.cr_notification_status = status.COMPLETED
    culprit.put()
    revert_status, _, _ = gerrit.RevertCulprit(culprit.key.urlsafe(), 'm/b/1',
                                               failure_type.COMPILE, 'compile',
                                               self.codereview_info)

    self.assertEquals(revert_status, services_constants.CREATED_BY_FINDIT)
    # Assertions have never worked properly because we were using mock 1.0.1.
    # After rolling to mock 2.0.0, which fixes assertions, these assertions now
    # fail. https://crbug.com/947753.
    # mock_send.assert_has_not_called()

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testCulpritIsARevert(self, mock_fn, _):
    repo_name = 'chromium'
    revision = 'rev1'

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.revert_of = 123456
    cl_info.commits.append(
        Commit('20001', 'rev1', [], datetime(2017, 2, 1, 0, 0, 0)))
    mock_fn.return_value = cl_info

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.put()

    revert_status, revert, reason = gerrit.RevertCulprit(
        culprit.key.urlsafe(), 'm/b/1', failure_type.COMPILE, 'compile',
        self.codereview_info)

    self.assertEquals(services_constants.SKIPPED, revert_status)
    self.assertEqual(services_constants.CULPRIT_IS_A_REVERT, reason)
    self.assertIsNone(revert)

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testAutoRevertOff(self, mock_fn, _):
    repo_name = 'chromium'
    revision = 'rev1'

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.auto_revert_off = True
    cl_info.commits.append(
        Commit('20001', 'rev1', [], datetime(2017, 2, 1, 0, 0, 0)))
    mock_fn.return_value = cl_info

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.put()

    revert_status, revert, reason = gerrit.RevertCulprit(
        culprit.key.urlsafe(), 'm/b/1', failure_type.COMPILE, 'compile',
        self.codereview_info)

    self.assertEquals(services_constants.SKIPPED, revert_status)
    self.assertEquals(services_constants.AUTO_REVERT_OFF, reason)
    self.assertIsNone(revert)

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=None)
  def testCommitRevertNoCodeReview(self, _):
    repo_name = 'chromium'
    revision = 'rev1'
    commit_position = 123

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.commits.append(
        Commit('20001', 'rev1', [], datetime(2017, 2, 1, 0, 0, 0)))

    culprit = WfSuspectedCL.Create(repo_name, revision, commit_position)
    revert_for_culprit = RevertCL()
    revert_change_id = '54321'
    revert_for_culprit.revert_cl_url = 'https://%s/q/%s' % (
        self.review_server_host, revert_change_id)
    culprit.revert_cl = revert_for_culprit
    culprit.revert_status = status.COMPLETED
    culprit.put()
    revert_status = services_constants.CREATED_BY_FINDIT
    self.assertEquals(
        services_constants.ERROR,
        gerrit.CommitRevert(
            SubmitRevertCLParameters(
                cl_key=culprit.key.urlsafe(), revert_status=revert_status),
            None))

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=_CODEREVIEW)
  @mock.patch.object(codereview_util, 'IsCodeReviewGerrit', return_value=False)
  def testSubmitRevertForRietveld(self, *_):
    repo_name = 'chromium'
    revision = 'rev1'
    commit_position = 123

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.commits.append(
        Commit('20001', 'rev1', [], datetime(2017, 2, 1, 0, 0, 0)))

    culprit = WfSuspectedCL.Create(repo_name, revision, commit_position)
    revert_for_culprit = RevertCL()
    revert_change_id = '54321'
    revert_for_culprit.revert_cl_url = 'https://%s/q/%s' % (
        self.review_server_host, revert_change_id)
    culprit.revert_cl = revert_for_culprit
    culprit.revert_status = status.COMPLETED
    culprit.put()

    revert_status = services_constants.CREATED_BY_FINDIT
    commit_status = gerrit.CommitRevert(
        SubmitRevertCLParameters(
            cl_key=culprit.key.urlsafe(), revert_status=revert_status),
        self.codereview_info)
    self.assertEqual(services_constants.SKIPPED, commit_status)

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=_CODEREVIEW)
  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 2, 1, 5, 0, 0))
  @mock.patch.object(rotations, 'current_sheriffs', return_value=['a@b.com'])
  @mock.patch.object(_CODEREVIEW, 'AddReviewers', return_value=True)
  @mock.patch.object(_CODEREVIEW, 'SubmitRevert')
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testSubmitRevertFailed(self, mock_fn, mock_commit, mock_add, *_):
    repo_name = 'chromium'
    revision = 'rev1'
    commit_position = 123

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.commits.append(
        Commit('20001', 'rev1', [], datetime(2017, 2, 1, 0, 0, 0)))
    mock_fn.return_value = cl_info
    mock_commit.return_value = False

    culprit = WfSuspectedCL.Create(repo_name, revision, commit_position)
    revert_for_culprit = RevertCL()
    revert_change_id = '54321'
    revert_for_culprit.revert_cl_url = 'https://%s/q/%s' % (
        self.review_server_host, revert_change_id)
    culprit.revert_cl = revert_for_culprit
    culprit.revert_status = status.COMPLETED
    culprit.put()

    revert_status = services_constants.CREATED_BY_FINDIT
    commit_status = gerrit.CommitRevert(
        SubmitRevertCLParameters(
            cl_key=culprit.key.urlsafe(), revert_status=revert_status),
        self.codereview_info)

    self.assertEqual(services_constants.ERROR, commit_status)
    mock_commit.assert_called_once_with(revert_change_id)

    culprit_link = ('https://analysis.chromium.org/waterfall/culprit?key=%s' %
                    culprit.key.urlsafe())
    false_positive_bug_link = gerrit.CreateFinditWrongBugLink(
        gerrit.FINDIT_BUILD_FAILURE_COMPONENT, culprit_link, revision)

    auto_revert_bug_query = urllib.urlencode({
        'status': 'Available',
        'components': 'Tools>Test>FindIt>Autorevert',
        'summary': 'Auto Revert failed on %s' % revision,
        'comment': 'Detail is %s' % culprit_link
    })
    auto_revert_bug_link = (
        'https://bugs.chromium.org/p/chromium/issues/entry?%s') % (
            auto_revert_bug_query)
    message = textwrap.dedent("""
        Sheriffs, CL owner or CL reviewers:
        Please submit this revert if it is correct.
        If it is a false positive, please abandon and report it
        at %s.
        If failed to submit the revert, please abandon it and report the failure
        at %s.

        For more information about Findit auto-revert: %s.

        Sheriffs, it'll be much appreciated if you could take a couple minutes
        to fill out this survey: %s.""") % (
        false_positive_bug_link, auto_revert_bug_link, gerrit._MANUAL_LINK,
        gerrit._SURVEY_LINK)
    mock_add.assert_called_once_with('54321', ['a@b.com'], message)

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=_CODEREVIEW)
  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 2, 1, 5, 0, 0))
  @mock.patch.object(rotations, 'current_sheriffs', return_value=['a@b.com'])
  @mock.patch.object(_CODEREVIEW, 'AddReviewers', return_value=True)
  @mock.patch.object(_CODEREVIEW, 'SubmitRevert')
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testSubmitRevertSucceed(self, mock_fn, mock_commit, mock_add, *_):
    repo_name = 'chromium'
    revision = 'rev1'
    commit_position = 123

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.commits.append(
        Commit('20001', 'rev1', [], datetime(2017, 2, 1, 0, 0, 0)))
    mock_fn.return_value = cl_info
    mock_commit.return_value = True

    culprit = WfSuspectedCL.Create(repo_name, revision, commit_position)
    revert_for_culprit = RevertCL()
    revert_change_id = '54321'
    revert_for_culprit.revert_cl_url = 'https://%s/q/%s' % (
        self.review_server_host, revert_change_id)
    culprit.revert_cl = revert_for_culprit
    culprit.revert_status = status.COMPLETED
    culprit.put()
    revert_status = services_constants.CREATED_BY_FINDIT
    commit_status = gerrit.CommitRevert(
        SubmitRevertCLParameters(
            cl_key=culprit.key.urlsafe(), revert_status=revert_status),
        self.codereview_info)

    self.assertEqual(services_constants.COMMITTED, commit_status)

    mock_commit.assert_called_once_with(revert_change_id)

    culprit_link = ('https://analysis.chromium.org/waterfall/culprit?key=%s' %
                    (culprit.key.urlsafe()))
    false_positive_bug_link = gerrit.CreateFinditWrongBugLink(
        gerrit.FINDIT_BUILD_FAILURE_COMPONENT, culprit_link, revision)
    message = textwrap.dedent("""
        Sheriffs, CL owner or CL reviewers:
        Please confirm this revert if it is correct.
        If it is a false positive, please reland the original CL and report this
        false positive at %s.

        For more information about Findit auto-revert: %s.

        Sheriffs, it'll be much appreciated if you could take a couple minutes
        to fill out this survey: %s.""") % (
        false_positive_bug_link, gerrit._MANUAL_LINK, gerrit._SURVEY_LINK)
    mock_add.assert_called_once_with(revert_change_id, ['a@b.com'], message)

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=None)
  def testSendNotificationForCulpritNoCodeReview(self, _):
    repo_name = 'chromium'
    revision = 'rev1'
    revert_status = services_constants.CREATED_BY_SHERIFF

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.put()

    parameters = SendNotificationForCulpritParameters(
        cl_key=culprit.key.urlsafe(),
        force_notify=False,
        revert_status=revert_status,
        failure_type=failure_type.COMPILE)
    self.assertFalse(
        gerrit.SendNotificationForCulprit(parameters, self.codereview_info))

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'PostMessage', return_value=True)
  def testSendNotificationForCulpritConfirm(self, mock_post, _):
    repo_name = 'chromium'
    revision = 'rev1'
    revert_status = services_constants.CREATED_BY_SHERIFF

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.put()

    culprit_link = culprit.GetCulpritLink()
    false_positive_bug_link = gerrit.CreateFinditWrongBugLink(
        gerrit.FINDIT_BUILD_FAILURE_COMPONENT, culprit_link, revision)

    parameters = SendNotificationForCulpritParameters(
        cl_key=culprit.key.urlsafe(),
        force_notify=False,
        revert_status=revert_status,
        failure_type=failure_type.COMPILE)

    self.assertTrue(
        gerrit.SendNotificationForCulprit(parameters, self.codereview_info))
    message = textwrap.dedent("""
    Findit (https://goo.gl/kROfz5) %s this CL at revision %s as the culprit for
    failures in the build cycles as shown on:
    https://analysis.chromium.org/waterfall/culprit?key=%s
    If it is a false positive, please report it at %s.""") % (
        'confirmed', self.culprit_commit_position, culprit.key.urlsafe(),
        false_positive_bug_link)
    mock_post.assert_called_once_with(self.review_change_id, message, False)

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'PostMessage', return_value=True)
  def testSendNotificationForCulprit(self, mock_post, _):
    repo_name = 'chromium'
    revision = 'rev1'
    revert_status = None

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.put()

    culprit_link = culprit.GetCulpritLink()
    false_positive_bug_link = gerrit.CreateFinditWrongBugLink(
        gerrit.FINDIT_BUILD_FAILURE_COMPONENT, culprit_link, revision)

    parameters = SendNotificationForCulpritParameters(
        cl_key=culprit.key.urlsafe(),
        force_notify=False,
        revert_status=revert_status,
        failure_type=failure_type.COMPILE)

    self.assertTrue(
        gerrit.SendNotificationForCulprit(parameters, self.codereview_info))
    message = textwrap.dedent("""
    Findit (https://goo.gl/kROfz5) %s this CL at revision %s as the culprit for
    failures in the build cycles as shown on:
    https://analysis.chromium.org/waterfall/culprit?key=%s
    If it is a false positive, please report it at %s.""") % (
        'identified', self.culprit_commit_position, culprit.key.urlsafe(),
        false_positive_bug_link)
    mock_post.assert_called_once_with(self.review_change_id, message, True)

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'QueryCls')
  def testExistCQedDependingChanges(self, mock_query, _):
    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.patchsets['12345-rev1'] = PatchSet('1', '12345-rev1', [])
    cl_info.patchsets['12345-rev1'] = PatchSet('2', '12345-rev2', [])

    cl_info_1 = ClInfo(self.review_server_host, '12346')
    cl_info_1.patchsets['12346-rev1'] = PatchSet('1', '12346-rev1',
                                                 ['unrelated'])
    cl_info_1.patchsets['12346-rev2'] = PatchSet('2', '12346-rev2',
                                                 ['unrelated'])

    cl_info_2 = ClInfo(self.review_server_host, '12347')
    cl_info_2.patchsets['12347-rev1'] = PatchSet('1', '12347-rev1',
                                                 ['12345-rev1'])
    cl_info_2.patchsets['12347-rev2'] = PatchSet('2', '12347-rev2',
                                                 ['unrelated'])

    cl_info_3 = ClInfo(self.review_server_host, '12348')
    cl_info_3.patchsets['12348-rev1'] = PatchSet('1', '12348-rev1',
                                                 ['unrelated'])
    cl_info_3.patchsets['12348-rev2'] = PatchSet('2', '12348-rev2',
                                                 ['unrelated'])
    mock_query.return_value = [cl_info, cl_info_1, cl_info_2, cl_info_3]
    self.assertTrue(gerrit.ExistCQedDependingChanges(self.codereview_info))

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'QueryCls')
  def testExistCQedDependingChangesNoDependingCL(self, mock_query, _):
    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.patchsets['12345-rev1'] = PatchSet('1', '12345-rev1', [])
    cl_info.patchsets['12345-rev1'] = PatchSet('2', '12345-rev2', [])
    mock_query.return_value = [cl_info]
    self.assertFalse(gerrit.ExistCQedDependingChanges(self.codereview_info))

  @mock.patch.object(gerrit, '_GetCodeReview', return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'QueryCls')
  def testExistCQedDependingChangesNoCLs(self, mock_query, _):
    mock_query.return_value = []
    self.assertFalse(gerrit.ExistCQedDependingChanges(self.codereview_info))

  def testExistCQedChangesDependingOnCulpritLoseInfo(self):
    self.assertFalse(gerrit.ExistCQedDependingChanges({}))

  def testExistCQedDependingChangesIncompleteInfo(self):
    self.assertFalse(
        gerrit.ExistCQedDependingChanges({
            'review_change_id': '123456'
        }))

  @mock.patch.object(
      codereview_util, 'GetCodeReviewForReview', return_value=_CODEREVIEW)
  def testGetCodeReview(self, _):
    self.assertIsNone(gerrit._GetCodeReview({}))
    self.assertEqual(
        _CODEREVIEW,
        gerrit._GetCodeReview({
            'review_server_host': 'review_server_host'
        }))
