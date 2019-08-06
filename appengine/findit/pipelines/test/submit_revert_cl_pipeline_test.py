# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from common.waterfall import failure_type
from infra_api_clients.codereview.cl_info import ClInfo
from infra_api_clients.codereview.cl_info import Commit
from infra_api_clients.codereview.gerrit import Gerrit
from libs import analysis_status as status
from libs import time_util
from model.base_suspected_cl import RevertCL
from model.wf_suspected_cl import WfSuspectedCL
from services import constants
from services import culprit_action
from services import gerrit
from services import git
from services.parameters import SubmitRevertCLParameters
from pipelines.submit_revert_cl_pipeline import SubmitRevertCLPipeline
from waterfall.test import wf_testcase


class SubmitRevertCLPipelineTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(SubmitRevertCLPipelineTest, self).setUp()
    self.culprit_commit_position = 123
    self.culprit_code_review_url = (
        'https://chromium-review.googlesource.com/12345')
    self.review_server_host = 'chromium-review.googlesource.com'
    self.review_change_id = '12345'

    def MockGetCodeReviewInfoForACommit(*_):
      culprit_info = {
          'commit_position': self.culprit_commit_position,
          'code_review_url': self.culprit_code_review_url,
          'review_server_host': self.review_server_host,
          'review_change_id': self.review_change_id,
          'author': {
              'email': 'author@chromium.org'
          }
      }
      return culprit_info

    self.mock(git, 'GetCodeReviewInfoForACommit',
              MockGetCodeReviewInfoForACommit)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 2, 1, 5, 0, 0))
  @mock.patch.object(culprit_action, '_CanCommitRevert', return_value=True)
  @mock.patch.object(gerrit, '_AddReviewers', return_value=True)
  @mock.patch.object(Gerrit, 'SubmitRevert')
  @mock.patch.object(Gerrit, 'GetClDetails')
  def testSubmitRevertSucceed(self, mock_fn, mock_commit, *_):
    repo_name = 'chromium'
    revision = 'rev1'
    commit_position = 123

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.commits.append(
        Commit('20001', 'rev1', [], datetime(2017, 2, 1, 0, 0, 0)))
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
    revert_status = constants.CREATED_BY_FINDIT
    pipeline_input = SubmitRevertCLParameters(
        cl_key=culprit.key.urlsafe(),
        revert_status=revert_status,
        failure_type=failure_type.COMPILE)
    pipeline = SubmitRevertCLPipeline(pipeline_input)
    self.assertEqual(constants.COMMITTED, pipeline.run(pipeline_input))

    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEqual(culprit.revert_submission_status, status.COMPLETED)

    mock_commit.assert_called_with(revert_change_id)

  def testLogUnexpectedAborting(self):
    repo_name = 'chromium'
    revision = 'rev1'
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_submission_status = status.RUNNING
    culprit.put()
    revert_status = constants.CREATED_BY_FINDIT
    pipeline_input = SubmitRevertCLParameters(
        cl_key=culprit.key.urlsafe(),
        revert_status=revert_status,
        failure_type=failure_type.COMPILE)
    SubmitRevertCLPipeline(pipeline_input).OnAbort(pipeline_input)
    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEquals(culprit.revert_submission_status, status.ERROR)

  def testLogUnexpectedAbortingNoChange(self):
    repo_name = 'chromium'
    revision = 'rev1'
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.put()

    revert_status = constants.CREATED_BY_FINDIT
    pipeline_input = SubmitRevertCLParameters(
        cl_key=culprit.key.urlsafe(),
        revert_status=revert_status,
        failure_type=failure_type.COMPILE)
    SubmitRevertCLPipeline(pipeline_input).OnAbort(pipeline_input)
    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertIsNone(culprit.revert_submission_status)

  def testLogUnexpectedAbortingPipelineIdNotMatch(self):
    repo_name = 'chromium'
    revision = 'rev1'
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.submit_revert_pipeline_id = 'pipeline_id'
    culprit.put()

    revert_status = constants.CREATED_BY_FINDIT
    pipeline_input = SubmitRevertCLParameters(
        cl_key=culprit.key.urlsafe(),
        revert_status=revert_status,
        failure_type=failure_type.COMPILE)
    pipeline = SubmitRevertCLPipeline(pipeline_input)
    pipeline.start_test()
    pipeline.OnAbort(pipeline_input)
    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEqual(culprit.submit_revert_pipeline_id, 'pipeline_id')