# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from issue_tracker import Issue

from libs import analysis_status
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall.flake import update_flake_bug_pipeline
from waterfall.test import wf_testcase


class UpdateFlakeToBugPipelineTest(wf_testcase.WaterfallTestCase):

  def testGetIssueWithoutMergeInto(self):
    issue_tracker = mock.Mock()
    expected_issue = Issue({'id': 123})
    issue_tracker.getIssue.return_value = expected_issue

    issue = update_flake_bug_pipeline._GetIssue(123, issue_tracker)
    self.assertEqual(expected_issue, issue)
    issue_tracker.assert_has_calls([mock.call.getIssue(123)])

  def testGetIssueWithMergeInto(self):
    issue_tracker = mock.Mock()
    expected_issue = Issue({'id': 345})
    issue_tracker.getIssue.side_effect = [
        Issue({'id': 123, 'mergedInto': {'issueId': 234}}),
        Issue({'id': 234, 'mergedInto': {'issueId': 345}}),
        expected_issue,
    ]

    issue = update_flake_bug_pipeline._GetIssue(123, issue_tracker)
    self.assertEqual(expected_issue, issue)
    issue_tracker.assert_has_calls(
        [mock.call.getIssue(123), mock.call.getIssue(234),
         mock.call.getIssue(345)])

  def testGetIssueWithMergeInACircle(self):
    issue_tracker = mock.Mock()
    expected_issue = Issue({'id': 123})
    issue_tracker.getIssue.side_effect = [
        Issue({'id': 123, 'mergedInto': {'issueId': 234}}),
        Issue({'id': 234, 'mergedInto': {'issueId': 123}}),
        expected_issue,
    ]

    issue = update_flake_bug_pipeline._GetIssue(123, issue_tracker)
    self.assertEqual(expected_issue, issue)
    issue_tracker.assert_has_calls(
        [mock.call.getIssue(123), mock.call.getIssue(234),
         mock.call.getIssue(123)])

  def testGenerateCommentUponError(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.ERROR
    comment = update_flake_bug_pipeline._GenerateComment(analysis)
    self.assertTrue('due to an error' in comment, comment)

  def testGenerateCommentWithCulprit(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.culprit = FlakeCulprit.Create('c', 'r', 123, 'http://', 0.6713)
    comment = update_flake_bug_pipeline._GenerateComment(analysis)
    self.assertTrue('culprit r123 with confidence 67.1%' in comment, comment)

  def testGenerateCommentWithSuspectedBuildHighConfidence(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.suspected_flake_build_number = 120
    analysis.confidence_in_suspected_build = 0.6641
    comment = update_flake_bug_pipeline._GenerateComment(analysis)
    self.assertTrue('started in build 120' in comment,
                    comment)

  def testGenerateCommentWithSuspectedBuildLowConfidence(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.suspected_flake_build_number = 120
    analysis.confidence_in_suspected_build = 0.3641
    comment = update_flake_bug_pipeline._GenerateComment(analysis)
    self.assertTrue('low flakiness' in comment, comment)

  def testGenerateCommentForLongstandingFlake(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    comment = update_flake_bug_pipeline._GenerateComment(analysis)
    self.assertTrue('longstanding one' in comment, comment)

  @mock.patch('waterfall.flake.update_flake_bug_pipeline.IssueTrackerAPI')
  def testNotUpdateBug(self, issue_tracker):
    analysis_not_completed = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis_not_completed.status = analysis_status.RUNNING
    analysis_without_bug = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis_without_bug.status = analysis_status.COMPLETED
    analysis_config_not_to_update = MasterFlakeAnalysis.Create(
        'm', 'b', 1, 's', 't')
    analysis_config_not_to_update.status = analysis_status.COMPLETED
    analysis_config_not_to_update.bug_id = 123
    analysis_config_not_to_update.algorithm_parameters = {
        'update_monorail_bug': False,
    }
    analysis_without_enough_data_points = MasterFlakeAnalysis.Create(
        'm', 'b', 1, 's', 't')
    analysis_without_enough_data_points.status = analysis_status.COMPLETED
    analysis_without_enough_data_points.bug_id = 123
    analysis_without_enough_data_points.algorithm_parameters = {
        'update_monorail_bug': True,
    }
    analysis_without_enough_data_points.data_points = [DataPoint()]

    analyses = [
        analysis_without_bug,
        analysis_config_not_to_update,
        analysis_without_enough_data_points
    ]
    for analysis in analyses:
      analysis.put()
      pipeline = update_flake_bug_pipeline.UpdateFlakeBugPipeline()
      self.assertFalse(pipeline.run(analysis.key.urlsafe()))
    issue_tracker.assert_not_called()

  @mock.patch('waterfall.flake.update_flake_bug_pipeline.IssueTrackerAPI')
  def testNoUpdateIfBugDeleted(self, issue_tracker):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.bug_id = 123
    analysis.algorithm_parameters = {'update_monorail_bug': True}
    analysis.data_points = [DataPoint(), DataPoint(), DataPoint()]
    analysis.put()

    mocked_instance = mock.Mock()
    mocked_instance.getIssue.return_value = None
    issue_tracker.return_value = mocked_instance
    pipeline = update_flake_bug_pipeline.UpdateFlakeBugPipeline()
    self.assertFalse(pipeline.run(analysis.key.urlsafe()))
    issue_tracker.assert_has_calls(
        [mock.call('chromium'), mock.call().getIssue(123)])

  @mock.patch('waterfall.flake.update_flake_bug_pipeline.IssueTrackerAPI')
  def testBugUpdated(self, issue_tracker):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.bug_id = 123
    analysis.algorithm_parameters = {'update_monorail_bug': True}
    analysis.data_points = [DataPoint(), DataPoint(), DataPoint()]
    analysis.put()

    dummy_issue = Issue({})
    mocked_instance = mock.Mock()
    mocked_instance.getIssue.return_value = dummy_issue
    issue_tracker.return_value = mocked_instance
    pipeline = update_flake_bug_pipeline.UpdateFlakeBugPipeline()
    self.assertTrue(pipeline.run(analysis.key.urlsafe()))
    issue_tracker.assert_has_calls(
        [mock.call('chromium'),
         mock.call().getIssue(123),
         mock.call().update(dummy_issue, mock.ANY, send_email=True)])
