# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
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
  def testOnCulpritIdentified(self, mocked_merge):
    project = 'chromium'
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    label = 'l'
    bug_id = 12345
    revision = 'r1000'
    commit_position = 1000

    issue = FlakeIssue.Create(project, bug_id)
    issue.put()

    flake = Flake.Create(project, step_name, test_name, label)
    flake.flake_issue_key = issue.key
    flake.put()

    culprit = FlakeCulprit.Create(project, revision, commit_position)
    culprit.put()

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.flake_key = flake.key
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    flake_analysis_actions.OnCulpritIdentified(analysis.key.urlsafe())

    mocked_merge.assert_called_once_with(issue.key, culprit.key)
