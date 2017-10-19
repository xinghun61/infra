# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock
import textwrap

from common import rotations
from infra_api_clients.codereview import codereview_util
from infra_api_clients.codereview.cl_info import ClInfo
from infra_api_clients.codereview.cl_info import Commit
from infra_api_clients.codereview.rietveld import Rietveld
from libs import analysis_status as status
from libs import time_util
from model.wf_suspected_cl import WfSuspectedCL
from services import revert
from pipelines.pipeline_inputs_and_outputs import CLKey
from pipelines.pipeline_inputs_and_outputs import CreateRevertCLPipelineInput
from waterfall import buildbot
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
    self.review_server_host = 'codereview.chromium.org'
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
      time_util, 'GetUTCNow', return_value=datetime(2017, 2, 1, 16, 0, 0))
  @mock.patch.object(_CODEREVIEW, 'PostMessage', return_value=True)
  @mock.patch.object(_CODEREVIEW, 'AddReviewers', return_value=True)
  @mock.patch.object(rotations, 'current_sheriffs', return_value=['a@b.com'])
  @mock.patch.object(
      codereview_util, 'GetCodeReviewForReview', return_value=_CODEREVIEW)
  @mock.patch.object(_CODEREVIEW, 'CreateRevert')
  @mock.patch.object(_CODEREVIEW, 'GetClDetails')
  def testRevertCLSucceed(self, mock_fn, mock_revert, *_):
    repo_name = 'chromium'
    revision = 'rev1'
    commit_position = 123
    build_id = 'm/b/123'

    cl_info = ClInfo(self.review_server_host, self.review_change_id)
    cl_info.commits.append(
        Commit('20001', 'rev1', datetime(2017, 2, 1, 0, 0, 0)))
    cl_info.owner_email = 'abc@chromium.org'
    mock_fn.return_value = cl_info
    mock_revert.return_value = '54321'

    culprit = WfSuspectedCL.Create(repo_name, revision, commit_position)
    culprit.builds = {'m/b/1': {'status': None}}
    culprit.put()

    pipeline_input = CreateRevertCLPipelineInput(
        cl_key=CLKey(
            repo_name=repo_name.decode('utf-8'),
            revision=revision.decode('utf-8')),
        build_id=build_id.decode('utf-8'))
    pipeline = CreateRevertCLPipeline(pipeline_input)
    revert_status = pipeline.run(pipeline_input)

    self.assertEquals(revert_status, revert.CREATED_BY_FINDIT)

    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEqual(culprit.revert_status, status.COMPLETED)
    self.assertIsNotNone(culprit.revert_cl)

    reason = textwrap.dedent("""
        Findit (https://goo.gl/kROfz5) identified CL at revision %s as the
        culprit for failures in the build cycles as shown on:
        https://findit-for-me.appspot.com/waterfall/culprit?key=%s\n
        Sample Failed Build: %s""") % (commit_position, culprit.key.urlsafe(),
                                       buildbot.CreateBuildUrl('m', 'b', '123'))
    mock_revert.assert_called_with(reason, self.review_change_id, '20001')

  @mock.patch.object(waterfall_config, 'GetActionSettings', return_value={})
  def testRevertTurnedOff(self, _):
    repo_name = 'chromium'
    revision = 'rev1'
    build_id = 'm/b/123'

    pipeline_input = CreateRevertCLPipelineInput(
        cl_key=CLKey(
            repo_name=repo_name.decode('utf-8'),
            revision=revision.decode('utf-8')),
        build_id=build_id.decode('utf-8'))
    pipeline = CreateRevertCLPipeline(pipeline_input)
    revert_status = pipeline.run(pipeline_input)

    self.assertEqual(revert.SKIPPED, revert_status)

  def testLogUnexpectedAborting(self):
    repo_name = 'chromium'
    revision = 'rev1'
    build_id = 'm/b/123'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_status = status.RUNNING
    culprit.put()

    pipeline_input = CreateRevertCLPipelineInput(
        cl_key=CLKey(
            repo_name=repo_name.decode('utf-8'),
            revision=revision.decode('utf-8')),
        build_id=build_id.decode('utf-8'))
    CreateRevertCLPipeline(pipeline_input).OnAbort(pipeline_input)
    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEquals(culprit.revert_status, status.ERROR)

  def testLogUnexpectedAbortingNoChange(self):
    repo_name = 'chromium'
    revision = 'rev1'
    build_id = 'm/b/123'
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.put()

    pipeline_input = CreateRevertCLPipelineInput(
        cl_key=CLKey(
            repo_name=repo_name.decode('utf-8'),
            revision=revision.decode('utf-8')),
        build_id=build_id.decode('utf-8'))
    CreateRevertCLPipeline(pipeline_input).OnAbort(pipeline_input)
    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertIsNone(culprit.revert_status)

  def testLogUnexpectedAbortingPipelineIdNotMatch(self):
    repo_name = 'chromium'
    revision = 'rev1'
    build_id = 'm/b/123'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_pipeline_id = 'pipeline_id'
    culprit.put()

    pipeline_input = CreateRevertCLPipelineInput(
        cl_key=CLKey(
            repo_name=repo_name.decode('utf-8'),
            revision=revision.decode('utf-8')),
        build_id=build_id.decode('utf-8'))
    pipeline = CreateRevertCLPipeline(pipeline_input)
    pipeline.start()
    pipeline.OnAbort(pipeline_input)
    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEqual(culprit.revert_pipeline_id, 'pipeline_id')
