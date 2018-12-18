# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
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
  def testOnCulpritIdentified(self, mocked_update_issues, mocked_merge):
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
    analysis.put()

    flake_analysis_actions.OnCulpritIdentified(analysis.key.urlsafe())

    mocked_merge.assert_called_once_with(issue.key, culprit.key)
    mocked_update_issues.assert_called_once_with(issue.key,
                                                 issue.merge_destination_key)

  @mock.patch.object(
      monorail_util, 'WasCreatedByFindit', side_effect=[True, False])
  @mock.patch.object(monorail_util, 'MergeDuplicateIssues')
  @mock.patch.object(monorail_util, 'GetMonorailIssueForIssueId')
  def testMergeOrSplitFlakeIssueByCulpritMergeIntoManuallyCreated(
      self, mocked_get_issue, mocked_merge_issues, _):
    project = 'chromium'
    duplicate_bug_id = 12344
    manually_created_bug_id = 12345
    revision = 'r1000'
    commit_position = 1000

    flake_issue = FlakeIssue.Create(project, manually_created_bug_id)
    flake_issue.put()
    culprit_flake_issue = FlakeIssue.Create(project, duplicate_bug_id)
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
        'id': str(manually_created_bug_id)
    })
    culprit_monorail_issue = Issue({
        'status': 'Available',
        'projectId': 'chromium',
        'id': str(duplicate_bug_id)
    })

    mocked_get_issue.side_effect = [
        culprit_monorail_issue, flake_monorail_issue
    ]

    (duplicate,
     destination) = flake_analysis_actions.MergeOrSplitFlakeIssueByCulprit(
         flake_issue.key, flake_culprit.key)

    mocked_merge_issues.assert_called_once_with(culprit_monorail_issue,
                                                flake_monorail_issue, mock.ANY)
    flake_culprit = flake_culprit.key.get()
    flake_issue = flake_issue.key.get()
    culprit_flake_issue = culprit_flake_issue.key.get()

    self.assertEqual(culprit_flake_issue.key, duplicate)
    self.assertEqual(flake_issue.key, destination)
    self.assertEqual(flake_issue.flake_culprit_key, flake_culprit.key)
    self.assertEqual(flake_issue.key, culprit_flake_issue.merge_destination_key)

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
    flake_issue.put()
    culprit_flake_issue = FlakeIssue.Create(project, merged_bug_id)
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
    flake_culprit = flake_culprit.key.get()
    flake_issue = flake_issue.key.get()

    self.assertEqual(flake_issue.key, duplicate)
    self.assertEqual(culprit_flake_issue.key, destination)
    self.assertEqual(flake_issue.merge_destination_key, culprit_flake_issue.key)

  @mock.patch.object(monorail_util, 'WasCreatedByFindit', return_value=True)
  @mock.patch.object(monorail_util, 'MergeDuplicateIssues')
  @mock.patch.object(monorail_util, 'GetMonorailIssueForIssueId')
  def testMergeOrSplitFlakeIssueByCulpritIssueClosed(self, mocked_get_issue,
                                                     mocked_merge_issues, _):
    project = 'chromium'
    closed_bug_id = 12344
    open_bug_id = 12345
    revision = 'r1000'
    commit_position = 1000

    flake_issue = FlakeIssue.Create(project, open_bug_id)
    flake_issue.put()
    culprit_flake_issue = FlakeIssue.Create(project, closed_bug_id)
    culprit_flake_issue.status = 'Fixed'
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
