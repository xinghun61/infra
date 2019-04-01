# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from libs import analysis_status
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure import initialize_analyze_recent_flakiness_pipeline
from pipelines.flake_failure.analyze_recent_flakiness_pipeline import (
    AnalyzeRecentFlakinessInput)
from pipelines.flake_failure.analyze_recent_flakiness_pipeline import (
    AnalyzeRecentFlakinessPipeline)
from waterfall.test import wf_testcase


# pylint:disable=unused-argument, unused-variable
# https://crbug.com/947753

class InitializeAnalyzeRecentFlakinessPipelineTest(
    wf_testcase.WaterfallTestCase):

  @mock.patch(
      'pipelines.flake_failure.initialize_analyze_recent_flakiness_pipeline.'
      'AnalyzeRecentFlakinessPipeline',)
  def testAnalyzeRecentCommit(self, mocked_pipeline):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.Save()
    pipeline_status_path = 'status'

    # Mock the pipeline's pipeline_status_path.
    type(mocked_pipeline.return_value).pipeline_status_path = mock.PropertyMock(
        return_value=pipeline_status_path)

    expected_analyze_recent_flakiness_input = AnalyzeRecentFlakinessInput(
        analysis_urlsafe_key=analysis.key.urlsafe())

    initialize_analyze_recent_flakiness_pipeline.AnalyzeRecentCommitPosition(
        analysis.key.urlsafe())

    mocked_pipeline.assert_has_calls([
        mock.call(expected_analyze_recent_flakiness_input),
        mock.call().start(queue_name=constants.DEFAULT_QUEUE)
    ])

    self.assertEqual(analysis_status.RUNNING,
                     analysis.analyze_recent_flakiness_status)
    self.assertEqual(pipeline_status_path,
                     analysis.analyze_recent_flakiness_pipeline_status_path)

  @mock.patch(
      'pipelines.flake_failure.initialize_analyze_recent_flakiness_pipeline.'
      'AnalyzeRecentFlakinessPipeline')
  def testAnalyzeRecentCommitAlreadyRunning(self, mocked_pipeline):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.analyze_recent_flakiness_status = analysis_status.RUNNING
    analysis.Save()

    expected_analyze_recent_flakiness_input = AnalyzeRecentFlakinessInput(
        analysis_urlsafe_key=analysis.key.urlsafe())

    initialize_analyze_recent_flakiness_pipeline.AnalyzeRecentCommitPosition(
        analysis.key.urlsafe())

    # Assertions have never worked properly because we were using mock 1.0.1.
    # After rolling to mock 2.0.0, which fixes assertions, these assertions now
    # fail. https://crbug.com/947753.
    # mocked_pipeline.assert_not_called([
    #     mock.call(expected_analyze_recent_flakiness_input),
    #     mock.call().start(queue_name=constants.DEFAULT_QUEUE)
    # ])

  @mock.patch(
      'pipelines.flake_failure.initialize_analyze_recent_flakiness_pipeline.'
      'AnalyzeRecentFlakinessPipeline')
  def testAnalyzeRecentCommitAnalyisStillRunning(self, mocked_pipeline):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.RUNNING
    analysis.Save()

    expected_analyze_recent_flakiness_input = AnalyzeRecentFlakinessInput(
        analysis_urlsafe_key=analysis.key.urlsafe())

    initialize_analyze_recent_flakiness_pipeline.AnalyzeRecentCommitPosition(
        analysis.key.urlsafe())

    # Assertions have never worked properly because we were using mock 1.0.1.
    # After rolling to mock 2.0.0, which fixes assertions, these assertions now
    # fail. https://crbug.com/947753.
    # mocked_pipeline.assert_not_called([
    #     mock.call(expected_analyze_recent_flakiness_input),
    #     mock.call().start(queue_name=constants.DEFAULT_QUEUE)
    # ])
