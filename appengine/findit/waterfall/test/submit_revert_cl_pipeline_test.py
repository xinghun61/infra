# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from infra_api_clients.codereview import codereview_util
from infra_api_clients.codereview.cl_info import ClInfo
from infra_api_clients.codereview.cl_info import Commit
from infra_api_clients.codereview.gerrit import Gerrit
from libs import analysis_status as status
from libs import time_util
from model.base_suspected_cl import RevertCL
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import revert as revert_util
from waterfall import submit_revert_cl_pipeline
from waterfall import suspected_cl_util
from waterfall import waterfall_config
from waterfall.submit_revert_cl_pipeline import SubmitRevertCLPipeline
from waterfall.test import wf_testcase

_CODEREVIEW = Gerrit('chromium-review.googlesource.com')


class SubmitRevertCLPipelineTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(SubmitRevertCLPipelineTest, self).setUp()
    self.culprit_commit_position = 123
    self.culprit_code_review_url = (
        'https://chromium-review.googlesource.com/12345')
    self.review_server_host = 'chromium-review.googlesource.com'
    self.review_change_id = '12345'

    def MockGetCulpritInfo(*_):
      culprit_info = {
          'commit_position': self.culprit_commit_position,
          'code_review_url': self.culprit_code_review_url,
          'review_server_host': self.review_server_host,
          'review_change_id': self.review_change_id
      }
      return culprit_info

    self.mock(suspected_cl_util, 'GetCulpritInfo', MockGetCulpritInfo)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 2, 1, 5, 0, 0))
  @mock.patch.object(
      codereview_util, 'GetCodeReviewForReview', return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'SubmitRevert')
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testSubmitRevertSucceed(self, mock_fn, mock_commit, *_):
    repo_name = 'chromium'
    revision = 'rev1'
    commit_position = 123

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.commits.append(
        Commit('20001', 'rev1', datetime(2017, 2, 1, 0, 0, 0)))
    mock_fn.return_value = cl_info
    mock_commit.return_value = True

    culprit = WfSuspectedCL.Create(repo_name, revision, commit_position)
    revert = RevertCL()
    revert_change_id = '54321'
    revert.revert_cl_url = 'https://%s/q/%s' % (self.review_server_host,
                                                revert_change_id)
    culprit.revert_cl = revert
    culprit.revert_status = status.COMPLETED
    culprit.put()
    revert_status = revert_util.CREATED_BY_FINDIT
    pipeline = SubmitRevertCLPipeline(repo_name, revision, revert_status)
    committed = pipeline.run(repo_name, revision, revert_status)

    self.assertTrue(committed)

    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEqual(culprit.revert_submission_status, status.COMPLETED)

    mock_commit.assert_called_with(revert_change_id)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 2, 4, 5, 0, 0))
  @mock.patch.object(
      codereview_util, 'GetCodeReviewForReview', return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'SubmitRevert')
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testSubmitRevertCulpritTooOld(self, mock_fn, mock_commit, *_):
    repo_name = 'chromium'
    revision = 'rev1'
    commit_position = 123

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.commits.append(
        Commit('20001', 'rev1', datetime(2017, 2, 1, 0, 0, 0)))
    mock_fn.return_value = cl_info
    mock_commit.return_value = True

    culprit = WfSuspectedCL.Create(repo_name, revision, commit_position)
    revert = RevertCL()
    revert_change_id = '54321'
    revert.revert_cl_url = 'https://%s/q/%s' % (self.review_server_host,
                                                revert_change_id)
    culprit.revert_cl = revert
    culprit.revert_status = status.COMPLETED
    culprit.put()

    revert_status = revert_util.CREATED_BY_FINDIT
    pipeline = SubmitRevertCLPipeline(repo_name, revision, revert_status)
    committed = pipeline.run(repo_name, revision, revert_status)

    self.assertFalse(committed)

    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEqual(culprit.revert_submission_status, status.SKIPPED)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 2, 1, 5, 0, 0))
  @mock.patch.object(
      codereview_util, 'GetCodeReviewForReview', return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'SubmitRevert')
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testSubmitRevertFailed(self, mock_fn, mock_commit, *_):
    repo_name = 'chromium'
    revision = 'rev1'
    commit_position = 123

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.commits.append(
        Commit('20001', 'rev1', datetime(2017, 2, 1, 0, 0, 0)))
    mock_fn.return_value = cl_info
    mock_commit.return_value = False

    culprit = WfSuspectedCL.Create(repo_name, revision, commit_position)
    revert = RevertCL()
    revert_change_id = '54321'
    revert.revert_cl_url = 'https://%s/q/%s' % (self.review_server_host,
                                                revert_change_id)
    culprit.revert_cl = revert
    culprit.revert_status = status.COMPLETED
    culprit.put()

    revert_status = revert_util.CREATED_BY_FINDIT
    pipeline = SubmitRevertCLPipeline(repo_name, revision, revert_status)
    committed = pipeline.run(repo_name, revision, revert_status)

    self.assertFalse(committed)
    mock_commit.assert_called_with(revert_change_id)

    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEqual(culprit.revert_submission_status, status.ERROR)

  @mock.patch.object(codereview_util, 'IsCodeReviewGerrit', return_value=False)
  def testSubmitRevertForRietveld(self, _):
    repo_name = 'chromium'
    revision = 'rev1'
    commit_position = 123

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.commits.append(
        Commit('20001', 'rev1', datetime(2017, 2, 1, 0, 0, 0)))

    culprit = WfSuspectedCL.Create(repo_name, revision, commit_position)
    revert = RevertCL()
    revert_change_id = '54321'
    revert.revert_cl_url = 'https://%s/q/%s' % (self.review_server_host,
                                                revert_change_id)
    culprit.revert_cl = revert
    culprit.revert_status = status.COMPLETED
    culprit.put()

    revert_status = revert_util.CREATED_BY_FINDIT
    pipeline = SubmitRevertCLPipeline(repo_name, revision, revert_status)
    committed = pipeline.run(repo_name, revision, revert_status)
    self.assertFalse(committed)

    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEqual(culprit.revert_submission_status, status.SKIPPED)

  @mock.patch.object(waterfall_config, 'GetActionSettings', return_value={})
  def testRevertTurnedOff(self, _):
    repo_name = 'chromium'
    revision = 'rev1'

    revert_status = revert_util.CREATED_BY_FINDIT
    pipeline = SubmitRevertCLPipeline(repo_name, revision, revert_status)
    committed = pipeline.run(repo_name, revision, revert_status)

    self.assertFalse(committed)

  @mock.patch.object(
      submit_revert_cl_pipeline,
      '_GetDailyNumberOfCommits',
      return_value=4)
  def testCommitExceedsLimit(self, _):
    repo_name = 'chromium'
    revision = 'rev1'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_cl = RevertCL()
    culprit.revert_status = status.COMPLETED
    culprit.put()

    revert_status = revert_util.CREATED_BY_FINDIT
    pipeline = SubmitRevertCLPipeline(repo_name, revision, revert_status)
    committed = pipeline.run(repo_name, revision, revert_status)

    self.assertFalse(committed)

  def testRevertHasCommitted(self):
    repo_name = 'chromium'
    revision = 'rev1'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_cl = RevertCL()
    culprit.revert_submission_status = status.COMPLETED
    culprit.put()

    revert_status = revert_util.CREATED_BY_FINDIT
    pipeline = SubmitRevertCLPipeline(repo_name, revision, revert_status)
    revert_status = pipeline.run(repo_name, revision, revert_status)

    self.assertFalse(revert_status)

  def testLogUnexpectedAborting(self):
    repo_name = 'chromium'
    revision = 'rev1'
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_submission_status = status.RUNNING
    culprit.put()
    revert_status = revert_util.CREATED_BY_FINDIT
    SubmitRevertCLPipeline(repo_name, revision,
                           revert_status)._LogUnexpectedAborting(True)
    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEquals(culprit.revert_submission_status, status.ERROR)

  def testLogUnexpectedAbortingNoChange(self):
    repo_name = 'chromium'
    revision = 'rev1'
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.put()

    revert_status = revert_util.CREATED_BY_FINDIT
    SubmitRevertCLPipeline(repo_name, revision,
                           revert_status)._LogUnexpectedAborting(True)
    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertIsNone(culprit.revert_submission_status)

  def testLogUnexpectedAbortingPipelineIdNotMatch(self):
    repo_name = 'chromium'
    revision = 'rev1'
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.submit_revert_pipeline_id = 'pipeline_id'
    culprit.put()

    revert_status = revert_util.CREATED_BY_FINDIT
    pipeline = SubmitRevertCLPipeline(repo_name, revision, revert_status)
    pipeline.start_test()
    pipeline._LogUnexpectedAborting(True)
    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEqual(culprit.submit_revert_pipeline_id, 'pipeline_id')

  def testUpdateCulprit(self):
    repo_name = 'chromium'
    revision = 'rev1'
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_submission_status = status.RUNNING
    culprit.submit_revert_pipeline_id = 'some_id'
    culprit.put()

    culprit = submit_revert_cl_pipeline._UpdateCulprit(repo_name, revision)
    self.assertEqual(culprit.submit_revert_pipeline_id, 'some_id')
