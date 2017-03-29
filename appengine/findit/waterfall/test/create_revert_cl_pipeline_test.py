# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from common import constants
from common import rotations
from infra_api_clients.codereview import codereview_util
from infra_api_clients.codereview.cl_info import ClInfo
from infra_api_clients.codereview.cl_info import Commit
from infra_api_clients.codereview.cl_info import Revert
from infra_api_clients.codereview.rietveld import Rietveld
from model import analysis_status as status
from model.base_suspected_cl import RevertCL
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import buildbot
from waterfall import create_revert_cl_pipeline
from waterfall import suspected_cl_util
from waterfall import waterfall_config
from waterfall.create_revert_cl_pipeline import CreateRevertCLPipeline
from waterfall.test import wf_testcase


_CODEREVIEW = Rietveld('codereview.chromium.org')


class CreateRevertCLPipelineTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(CreateRevertCLPipelineTest, self).setUp()
    self.culprit_commit_position = 123
    self.culprit_code_review_url = 'https://codereview.chromium.org/12345'
    self.code_review_server_hostname = 'codereview.chromium.org'
    self.change_id = '12345'

    def MockGetCulpritInfo(*_):
      return (
          self.culprit_commit_position,
          self.culprit_code_review_url,
          self.change_id
      )
    self.mock(suspected_cl_util, 'GetCulpritInfo',
              MockGetCulpritInfo)

  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=[123])
  @mock.patch.object(_CODEREVIEW, 'AddReviewers', return_value=True)
  @mock.patch.object(_CODEREVIEW, 'CreateRevert', return_value='54321')
  @mock.patch.object(rotations, 'current_sheriffs', return_value=['a@b.com'])
  @mock.patch.object(codereview_util, 'GetCodeReviewForReview',
                     return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testRevertCLSucceed(self, mock_fn, *_):
    repo_name = 'chromium'
    revision = 'rev1'

    cl_info = ClInfo(self.code_review_server_hostname, self.change_id)
    cl_info.commits.append(
      Commit('20001', 'rev1', datetime(2017, 2, 1, 0, 0, 0)))
    mock_fn.return_value = cl_info

    WfSuspectedCL.Create(repo_name, revision, 123).put()
    pipeline = CreateRevertCLPipeline(
        'm', 'b', 123, repo_name, revision)
    revert_status = pipeline.run('m', 'b', 123, repo_name, revision)

    self.assertEquals(
        revert_status, create_revert_cl_pipeline.CREATED_BY_FINDIT)

    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEqual(culprit.revert_status, status.COMPLETED)
    self.assertIsNotNone(culprit.revert_cl)

  @mock.patch.object(codereview_util, 'GetCodeReviewForReview',
                     return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testSheriffRevertedIt(self, mock_fn, *_):
    repo_name = 'chromium'
    revision = 'rev1'

    cl_info = ClInfo(self.code_review_server_hostname, self.change_id)
    cl_info.commits.append(
      Commit('20001', 'rev1', datetime(2017, 2, 1, 0, 0, 0)))
    revert_cl = ClInfo('revert_review_host', '123V3137')
    cl_info.reverts.append(
      Revert('20001', revert_cl, 'a@b', datetime(2017, 2, 1, 1, 0, 0))
    )
    mock_fn.return_value = cl_info

    WfSuspectedCL.Create(repo_name, revision, 123).put()

    pipeline = CreateRevertCLPipeline('m', 'b', 123, repo_name, revision)
    revert_status = pipeline.run('m', 'b', 123, repo_name, revision)

    self.assertEquals(
      revert_status, create_revert_cl_pipeline.CREATED_BY_SHERIFF)

    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertIsNone(culprit.revert_status, status.COMPLETED)
    self.assertIsNone(culprit.revert_cl)

  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=[123])
  @mock.patch.object(_CODEREVIEW, 'AddReviewers', return_value=True)
  @mock.patch.object(rotations, 'current_sheriffs', return_value=['a@b.com'])
  @mock.patch.object(codereview_util, 'GetCodeReviewForReview',
                     return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testRevertCLNotSaved(self, mock_fn, *_):
    repo_name = 'chromium'
    revision = 'rev1'

    cl_info = ClInfo(self.code_review_server_hostname, self.change_id)
    cl_info.commits.append(
      Commit('20001', 'rev1', datetime(2017, 2, 1, 0, 0, 0)))
    revert_cl = ClInfo('revert_review_host', '123V3127')
    revert_cl.url = 'https://codereview.chromium.org/54321'
    cl_info.reverts.append(
      Revert('20001', revert_cl, constants.DEFAULT_SERVICE_ACCOUNT,
             datetime(2017, 2, 1, 1, 0, 0)))
    mock_fn.return_value = cl_info

    WfSuspectedCL.Create(repo_name, revision, 123).put()
    pipeline = CreateRevertCLPipeline('m', 'b', 123, repo_name, revision)
    revert_status = pipeline.run('m', 'b', 123, repo_name, revision)

    self.assertEquals(
        revert_status, create_revert_cl_pipeline.CREATED_BY_FINDIT)

    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEqual(culprit.revert_status, status.COMPLETED)
    self.assertIsNotNone(culprit.revert_cl)

  @mock.patch.object(buildbot, 'GetBuildResult',
                     return_value=buildbot.FAILURE)
  @mock.patch.object(buildbot, 'GetBuildDataFromBuildMaster',
                     return_value='{"data": "data"}')
  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=[124])
  @mock.patch.object(_CODEREVIEW, 'AddReviewers', return_value=True)
  @mock.patch.object(rotations, 'current_sheriffs', return_value=['a@b.com'])
  @mock.patch.object(codereview_util, 'GetCodeReviewForReview',
                     return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testAddedReviewerFailedBefore(self, mock_fn, *_):
    repo_name = 'chromium'
    revision = 'rev1'

    cl_info = ClInfo(self.code_review_server_hostname, self.change_id)
    cl_info.commits.append(
      Commit('20001', 'rev1', datetime(2017, 2, 1, 0, 0, 0)))
    revert_cl = ClInfo('revert_review_host', '123V3127')
    revert_cl.url = 'https://codereview.chromium.org/54321'
    cl_info.reverts.append(
      Revert('20001', revert_cl, constants.DEFAULT_SERVICE_ACCOUNT,
             datetime(2017, 2, 1, 1, 0, 0)))
    mock_fn.return_value = cl_info

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_cl = RevertCL()
    culprit.revert_status = status.RUNNING
    culprit.put()
    pipeline = CreateRevertCLPipeline('m', 'b', 123, repo_name, revision)
    revert_status = pipeline.run('m', 'b', 123, repo_name, revision)

    self.assertEquals(
        revert_status, create_revert_cl_pipeline.CREATED_BY_FINDIT)

    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEqual(culprit.revert_status, status.COMPLETED)
    self.assertIsNotNone(culprit.revert_cl)

  @mock.patch.object(buildbot, 'GetBuildResult',
                     return_value=buildbot.SUCCESS)
  @mock.patch.object(buildbot, 'GetBuildDataFromBuildMaster',
                     return_value='{"data": "data"}')
  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=[124])
  @mock.patch.object(codereview_util, 'GetCodeReviewForReview',
                     return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testLatestBuildSucceeded(self, mock_fn, *_):
    repo_name = 'chromium'
    revision = 'rev1'

    cl_info = ClInfo(self.code_review_server_hostname, self.change_id)
    cl_info.commits.append(
      Commit('20001', 'rev1', datetime(2017, 2, 1, 0, 0, 0)))
    revert_cl = ClInfo('revert_review_host', '123V3127')
    revert_cl.url = 'https://codereview.chromium.org/54321'
    cl_info.reverts.append(
      Revert('20001', revert_cl, constants.DEFAULT_SERVICE_ACCOUNT,
             datetime(2017, 2, 1, 1, 0, 0)))
    mock_fn.return_value = cl_info

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_cl = RevertCL()
    culprit.revert_status = status.RUNNING
    culprit.put()
    pipeline = CreateRevertCLPipeline('m', 'b', 123, repo_name, revision)
    revert_status = pipeline.run('m', 'b', 123, repo_name, revision)

    self.assertEquals(
        revert_status, create_revert_cl_pipeline.SKIPPED)

    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEqual(culprit.revert_status, status.SKIPPED)
    self.assertIsNotNone(culprit.revert_cl)

  @mock.patch.object(waterfall_config, 'GetActionSettings',
                     return_value={})
  def testRevertTurnedOff(self, _):
    repo_name = 'chromium'
    revision = 'rev1'

    pipeline = CreateRevertCLPipeline('m', 'b', 123, repo_name, revision)
    revert_status = pipeline.run('m', 'b', 123, repo_name, revision)

    self.assertIsNone(revert_status)

  def testRevertHasCompleted(self):
    repo_name = 'chromium'
    revision = 'rev1'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_cl = RevertCL()
    culprit.revert_status = status.COMPLETED
    culprit.put()

    pipeline = CreateRevertCLPipeline('m', 'b', 123, repo_name, revision)
    revert_status = pipeline.run('m', 'b', 123, repo_name, revision)

    self.assertEquals(
      revert_status, create_revert_cl_pipeline.CREATED_BY_FINDIT)

  def testLogUnexpectedAborting(self):
    repo_name = 'chromium'
    revision = 'rev1'
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_status = status.RUNNING
    culprit.put()

    CreateRevertCLPipeline(
        'm', 'b', 123, repo_name, revision)._LogUnexpectedAborting(True)
    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEquals(culprit.revert_status, status.ERROR)

  def testLogUnexpectedAbortingNoChange(self):
    repo_name = 'chromium'
    revision = 'rev1'
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.put()

    CreateRevertCLPipeline(
        'm', 'b', 123, repo_name, revision)._LogUnexpectedAborting(True)
    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertIsNone(culprit.revert_status)

  @mock.patch.object(buildbot, 'GetBuildDataFromBuildMaster',
                     return_value=None)
  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=[124])
  def testIsLatestBuildFailedGetBuildDataFailed(self, *_):
    self.assertFalse(
        create_revert_cl_pipeline._LatestBuildFailed('m', 'b', 123))

  @mock.patch.object(buildbot, 'GetBuildDataFromBuildMaster',
                     return_value='{"data": "data"}')
  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds',
                     return_value=[125, 124])
  @mock.patch.object(buildbot, 'GetBuildResult')
  def testIsLatestBuildFailedPassedThenFailed(self, mock_fn, *_):
    mock_fn.side_effect = [buildbot.FAILURE, buildbot.SUCCESS]
    self.assertFalse(
        create_revert_cl_pipeline._LatestBuildFailed('m', 'b', 123))
