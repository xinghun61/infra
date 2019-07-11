# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from libs import time_util
from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from monorail_api import Comment
from monorail_api import Issue
from services import flake_issue_util
from services import monorail_util
from services.actions import flake_analysis_actions
from waterfall.test.wf_testcase import WaterfallTestCase


class FlakeAnalysisActionsTest(WaterfallTestCase):

  def testMergeOrSplitFlakeIssueByCulprit(self):
    project = 'chromium'
    bug_id = 12345
    revision = 'r1000'
    commit_position = 1000
    issue = FlakeIssue.Create(project, bug_id)
    issue.put()

    culprit = FlakeCulprit.Create(project, revision, commit_position)
    culprit.put()

    flake_analysis_actions.MergeOrSplitFlakeIssueByCulprit(
        issue.key, culprit.key)

    issue = issue.key.get()
    culprit = culprit.key.get()

    self.assertEqual(culprit.key, issue.flake_culprit_key)
    self.assertEqual(issue.key, culprit.flake_issue_key)

  @mock.patch.object(flake_analysis_actions, 'MergeOrSplitFlakeIssueByCulprit')
  @mock.patch.object(flake_issue_util, 'UpdateIssueLeaves')
  @mock.patch.object(flake_analysis_actions, 'UpdateMonorailBugWithCulprit')
  def testOnCulpritIdentified(self, mocked_update_monorail,
                              mocked_update_issues, mocked_merge):
    project = 'chromium'
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    label = 'l'
    bug_id = 12345
    merged_bug_id = 12344
    revision = 'r1000'
    commit_position = 1000

    merged_issue = FlakeIssue.Create(project, merged_bug_id)
    merged_issue.put()
    issue = FlakeIssue.Create(project, bug_id)
    issue.merge_destination_key = merged_issue.key
    issue.put()

    flake = Flake.Create(project, step_name, test_name, label)
    flake.flake_issue_key = issue.key
    flake.put()

    culprit = FlakeCulprit.Create(project, revision, commit_position)
    culprit.flake_issue_key = merged_issue.key
    culprit.put()

    mocked_merge.return_value = (issue.key, merged_issue.key)

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.flake_key = flake.key
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.confidence_in_culprit = 0.9
    analysis.put()

    flake_analysis_actions.OnCulpritIdentified(analysis.key.urlsafe())

    mocked_merge.assert_called_once_with(issue.key, culprit.key)
    mocked_update_issues.assert_called_once_with(issue.key,
                                                 issue.merge_destination_key)
    mocked_update_monorail.assert_called_once_with(analysis.key.urlsafe())

  @mock.patch.object(
      time_util, 'GetDateDaysBeforeNow', return_value=datetime(2019, 1, 3))
  def testMergeOrSplitFlakeIssueByCulpritFlakeIssueClosedLongAgo(self, _):
    project = 'chromium'
    duplicate_bug_id = 12344
    manually_created_bug_id = 12345
    revision = 'r1000'
    commit_position = 1000

    flake_issue = FlakeIssue.Create(project, manually_created_bug_id)
    flake_issue.status = 'Fixed'
    flake_issue.last_updated_time_in_monorail = datetime(2019, 1, 1)
    flake_issue.put()
    culprit_flake_issue = FlakeIssue.Create(project, duplicate_bug_id)
    culprit_flake_issue.put()

    flake_culprit = FlakeCulprit.Create(project, revision, commit_position)
    flake_culprit.flake_issue_key = culprit_flake_issue.key
    flake_culprit.put()

    (duplicate,
     destination) = flake_analysis_actions.MergeOrSplitFlakeIssueByCulprit(
         flake_issue.key, flake_culprit.key)

    self.assertIsNone(duplicate)
    self.assertIsNone(destination)

  @mock.patch.object(monorail_util, 'WasCreatedByFindit', return_value=True)
  @mock.patch.object(monorail_util, 'MergeDuplicateIssues')
  @mock.patch.object(monorail_util, 'GetMonorailIssueForIssueId')
  def testMergeOrSplitFlakeIssueByCulpritMergedIntoCulpritFlakeIssue(
      self, mocked_get_issue, mocked_merge_issues, _):
    project = 'chromium'
    duplicate_bug_id = 12344
    merged_bug_id = 12345
    revision = 'r1000'
    commit_position = 1000

    flake_issue = FlakeIssue.Create(project, duplicate_bug_id)
    flake_issue.status = 'Untriaged'
    flake_issue.put()
    culprit_flake_issue = FlakeIssue.Create(project, merged_bug_id)
    culprit_flake_issue.status = 'Started'
    culprit_flake_issue.put()

    flake_culprit = FlakeCulprit.Create(project, revision, commit_position)
    flake_culprit.flake_issue_key = culprit_flake_issue.key
    flake_culprit.put()

    # Even though the flake issue associated with the culprit was identified
    # first, the incoming flake issue was manually created. Merge into the
    # manually created one.
    flake_monorail_issue = Issue({
        'status': 'Available',
        'projectId': 'chromium',
        'id': str(duplicate_bug_id)
    })
    culprit_monorail_issue = Issue({
        'status': 'Available',
        'projectId': 'chromium',
        'id': str(merged_bug_id)
    })

    mocked_get_issue.side_effect = [
        culprit_monorail_issue, flake_monorail_issue
    ]

    (duplicate,
     destination) = flake_analysis_actions.MergeOrSplitFlakeIssueByCulprit(
         flake_issue.key, flake_culprit.key)

    mocked_merge_issues.assert_called_once_with(
        flake_monorail_issue, culprit_monorail_issue, mock.ANY)
    flake_issue = flake_issue.key.get()

    self.assertEqual(flake_issue.key, duplicate)
    self.assertEqual(culprit_flake_issue.key, destination)
    self.assertEqual(flake_issue.merge_destination_key, culprit_flake_issue.key)

  @mock.patch.object(
      time_util, 'GetDateDaysBeforeNow', return_value=datetime(2019, 1, 2))
  @mock.patch.object(monorail_util, 'WasCreatedByFindit', return_value=True)
  @mock.patch.object(monorail_util, 'MergeDuplicateIssues')
  @mock.patch.object(monorail_util, 'GetMonorailIssueForIssueId')
  def testMergeOrSplitFlakeIssueByCulpritIssueClosed(self, mocked_get_issue,
                                                     mocked_merge_issues, *_):
    project = 'chromium'
    closed_bug_id = 12344
    open_bug_id = 12345
    revision = 'r1000'
    commit_position = 1000

    flake_issue = FlakeIssue.Create(project, open_bug_id)
    flake_issue.put()
    culprit_flake_issue = FlakeIssue.Create(project, closed_bug_id)
    culprit_flake_issue.status = 'Fixed'
    culprit_flake_issue.last_updated_time_in_monorail = datetime(2019, 1, 1)
    culprit_flake_issue.put()

    flake_culprit = FlakeCulprit.Create(project, revision, commit_position)
    flake_culprit.flake_issue_key = culprit_flake_issue.key
    flake_culprit.put()

    # Even though the flake issue associated with the culprit was identified
    # first, it has been closed. FlakeCulprit should have its flake issue
    # updated to the incoming one.
    flake_monorail_issue = Issue({
        'status': 'Available',
        'projectId': 'chromium',
        'id': str(open_bug_id)
    })
    culprit_monorail_issue = Issue({
        'status': 'Fixed',
        'projectId': 'chromium',
        'id': str(closed_bug_id)
    })

    mocked_get_issue.side_effect = [
        culprit_monorail_issue, flake_monorail_issue
    ]

    (duplicate,
     destination) = flake_analysis_actions.MergeOrSplitFlakeIssueByCulprit(
         flake_issue.key, flake_culprit.key)

    mocked_merge_issues.assert_not_called()
    flake_culprit = flake_culprit.key.get()

    self.assertIsNone(duplicate)
    self.assertIsNone(destination)
    self.assertIsNone(flake_issue.merge_destination_key)
    self.assertEqual(flake_issue.key, flake_culprit.flake_issue_key)

  @mock.patch.object(monorail_util, 'WasCreatedByFindit', return_value=True)
  @mock.patch.object(monorail_util, 'MergeDuplicateIssues')
  @mock.patch.object(monorail_util, 'GetMonorailIssueForIssueId')
  def testMergeOrSplitFlakeIssueByCulpritIssueAlreadyMerged(
      self, mocked_get_issue, mocked_merge_issues, _):
    # Culprit's flake issue 12344 was already merged into 12346.
    # Incoming flake issue's id is 12345 and is expected to be merged as well.
    project = 'chromium'
    merged_bug_id = 12344
    open_bug_id = 12345
    destination_bug_id = 12346
    revision = 'r1000'
    commit_position = 1000

    flake_issue = FlakeIssue.Create(project, open_bug_id)
    flake_issue.put()

    destination_issue = FlakeIssue.Create(project, destination_bug_id)
    destination_issue.put()

    culprit_flake_issue = FlakeIssue.Create(project, merged_bug_id)
    culprit_flake_issue.status = 'Merged'
    culprit_flake_issue.merge_destination_key = destination_issue.key
    culprit_flake_issue.put()

    flake_culprit = FlakeCulprit.Create(project, revision, commit_position)
    flake_culprit.flake_issue_key = culprit_flake_issue.key
    flake_culprit.put()

    flake_monorail_issue = Issue({
        'status': 'Available',
        'projectId': 'chromium',
        'id': str(open_bug_id)
    })
    destination_monorail_issue = Issue({
        'status': 'Available',
        'projectId': 'chromium',
        'id': str(destination_bug_id)
    })

    mocked_get_issue.side_effect = [
        destination_monorail_issue,
        flake_monorail_issue,
    ]

    (duplicate,
     destination) = flake_analysis_actions.MergeOrSplitFlakeIssueByCulprit(
         flake_issue.key, flake_culprit.key)

    mocked_merge_issues.assert_called_once_with(
        flake_monorail_issue, destination_monorail_issue, mock.ANY)
    flake_issue = flake_issue.key.get()

    self.assertEqual(flake_issue.key, duplicate)
    self.assertEqual(destination_issue.key, destination)
    self.assertEqual(destination_issue.key, flake_issue.merge_destination_key)

  @mock.patch.object(
      flake_issue_util,
      'GetRemainingPostAnalysisDailyBugUpdatesCount',
      return_value=1)
  @mock.patch.object(monorail_util, 'GetMonorailIssueForIssueId')
  @mock.patch.object(monorail_util, 'GetComments')
  @mock.patch.object(monorail_util, 'UpdateIssueWithIssueGenerator')
  def testUpdateMonorailBugWithCulprit(self, mock_update, mock_comments,
                                       mock_get_issue, *_):
    project = 'chromium'
    bug_id = 12345
    step_name = 's'
    test_name = 't'
    label = 'l'

    flake_issue = FlakeIssue.Create(project, bug_id)
    flake_issue.put()

    flake = Flake.Create(project, step_name, test_name, label)
    flake.flake_issue_key = flake_issue.key
    flake.put()

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.flake_key = flake.key
    analysis.put()

    mock_comments.return_value = [
        Comment({
            'author': {
                'name': 'someone@chromium.org'
            },
            'content': '',
            'published': None,
            'id': '12345',
        }),
    ]
    mock_get_issue.return_value = Issue({
        'status': 'Available',
        'projectId': 'chromium',
        'id': str(bug_id),
        'state': 'open'
    })
    flake_analysis_actions.UpdateMonorailBugWithCulprit(analysis.key.urlsafe())

    mock_update.assert_called_once_with(bug_id, mock.ANY)
    self.assertIsNotNone(flake_issue.last_updated_time_with_analysis_results)

  @mock.patch.object(flake_analysis_actions, 'MergeOrSplitFlakeIssueByCulprit')
  @mock.patch.object(flake_analysis_actions, 'UpdateMonorailBugWithCulprit')
  def testOnCulpritIdentifiedAttachCulpritFlakeIssue(
      self, mocked_update_monorail, mocked_merge):
    project = 'chromium'
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    label = 'l'
    merged_bug_id = 12344
    revision = 'r1000'
    commit_position = 1000

    merged_issue = FlakeIssue.Create(project, merged_bug_id)
    merged_issue.put()

    flake = Flake.Create(project, step_name, test_name, label)
    flake.put()

    culprit = FlakeCulprit.Create(project, revision, commit_position)
    culprit.flake_issue_key = merged_issue.key
    culprit.put()

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.flake_key = flake.key
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.confidence_in_culprit = 0.9
    analysis.put()

    flake_analysis_actions.OnCulpritIdentified(analysis.key.urlsafe())

    self.assertFalse(mocked_merge.called)
    mocked_update_monorail.assert_called_once_with(analysis.key.urlsafe())
    flake = flake.key.get()
    self.assertEqual(merged_issue.key, flake.flake_issue_key)

  def testAttachCulpritFlakeIssueToFlakeNoFlake(self):
    self.assertIsNone(
        flake_analysis_actions._AttachCulpritFlakeIssueToFlake(None, None))

  def testAttachCulpritFlakeIssueToFlakeNoCulpritFlakeIssue(self):
    project = 'chromium'
    step_name = 's'
    test_name = 't'
    label = 'l'
    revision = 'r1000'
    commit_position = 1000

    flake = Flake.Create(project, step_name, test_name, label)
    flake.put()

    culprit = FlakeCulprit.Create(project, revision, commit_position)
    culprit.put()
    self.assertIsNone(
        flake_analysis_actions._AttachCulpritFlakeIssueToFlake(
            flake, culprit.key))
