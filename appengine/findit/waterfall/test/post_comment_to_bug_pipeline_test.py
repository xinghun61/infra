# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from issue_tracker import Issue

from waterfall import post_comment_to_bug_pipeline
from waterfall.test import wf_testcase


class PostCommentToBugPipelineTest(wf_testcase.WaterfallTestCase):

  def testGetIssueWithoutMergeInto(self):
    issue_tracker = mock.Mock()
    expected_issue = Issue({})
    issue_tracker.getIssue.return_value = expected_issue

    issue = post_comment_to_bug_pipeline._GetIssue(123, issue_tracker)
    self.assertEqual(expected_issue, issue)
    issue_tracker.assert_has_calls([mock.call.getIssue(123)])

  def testGetIssueWithMergeInto(self):
    issue_tracker = mock.Mock()
    expected_issue = Issue({})
    issue_tracker.getIssue.side_effect = [
        Issue({'mergedInto': {'issueId': 234}}),
        Issue({'mergedInto': {'issueId': 345}}),
        expected_issue,
    ]

    issue = post_comment_to_bug_pipeline._GetIssue(123, issue_tracker)
    self.assertEqual(expected_issue, issue)
    issue_tracker.assert_has_calls(
        [mock.call.getIssue(123), mock.call.getIssue(234),
         mock.call.getIssue(345)])

  @mock.patch('waterfall.post_comment_to_bug_pipeline.IssueTrackerAPI')
  def testPostCommentToBug(self, issue_tracker):
    dummy_issue = Issue({})
    mocked_instance = mock.Mock()
    mocked_instance.getIssue.return_value = dummy_issue
    issue_tracker.return_value = mocked_instance
    pipeline = post_comment_to_bug_pipeline.PostCommentToBugPipeline()
    pipeline.run(123, 'comment', ['label'])
    issue_tracker.assert_has_calls(
        [mock.call('chromium'),
         mock.call().getIssue(123),
         mock.call().update(dummy_issue, 'comment', send_email=True)])
    self.assertEqual(['label'], dummy_issue.labels)

  @mock.patch('waterfall.post_comment_to_bug_pipeline.IssueTrackerAPI')
  def testPostCommentToBugWhenDeleted(self, issue_tracker):
    mocked_instance = mock.Mock()
    mocked_instance.getIssue.return_value = None
    issue_tracker.return_value = mocked_instance
    pipeline = post_comment_to_bug_pipeline.PostCommentToBugPipeline()
    pipeline.run(123, 'comment', ['label'])
    issue_tracker.assert_has_calls(
        [mock.call('chromium'),
         mock.call().getIssue(123)])
