# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dto.create_and_submit_revert_input import CreateAndSubmitRevertInput
from gae_libs.pipelines import pipeline_handlers
from pipelines.flake_failure.create_and_submit_revert_pipeline import (
    CreateAndSubmitRevertPipeline)
from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from services.flake_failure import culprit_util
from waterfall.test.wf_testcase import WaterfallTestCase


class CreateAndSubmitRevertPipelineTest(WaterfallTestCase):

  app_module = pipeline_handlers._APP

  @mock.patch.object(culprit_util, 'CreateAndSubmitRevert')
  def testRunImpl(self, revert_fn):
    build_key = 'mock_build_key'
    repo = 'chromium'
    rev = 'rev1'
    commit_position = 100

    culprit = FlakeCulprit.Create(repo, rev, commit_position)
    culprit.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    pipeline_input = CreateAndSubmitRevertInput(
        analysis_urlsafe_key=analysis.key.urlsafe(), build_key=build_key)
    pipeline_job = CreateAndSubmitRevertPipeline(pipeline_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    revert_fn.assert_called_once_with(pipeline_input, pipeline_job.pipeline_id)

  @mock.patch.object(culprit_util, 'AbortCreateAndSubmitRevert')
  def testAbort(self, abort_fn):
    build_key = 'mock_build_key'
    repo = 'chromium'
    rev = 'rev1'
    commit_position = 100

    culprit = FlakeCulprit.Create(repo, rev, commit_position)
    culprit.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    pipeline_input = CreateAndSubmitRevertInput(
        analysis_urlsafe_key=analysis.key.urlsafe(), build_key=build_key)
    pipeline_job = CreateAndSubmitRevertPipeline(pipeline_input)
    pipeline_job.OnAbort(pipeline_input)

    abort_fn.assert_called_once_with(pipeline_input, pipeline_job.pipeline_id)
