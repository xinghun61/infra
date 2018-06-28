# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.testcase import TestCase
from model.flake.detection.flake_issue import FlakeIssue


class FlakeIssueTest(TestCase):

  def testGetId(self):
    monorail_project = 'chromium'
    issue_id = 123
    self.assertEqual(
        'chromium@123',
        FlakeIssue.GetId(monorail_project=monorail_project, issue_id=issue_id))

  def testCreate(self):
    monorail_project = 'chromium'
    issue_id = 123
    flake_issue = FlakeIssue.Create(
        monorail_project=monorail_project, issue_id=issue_id)

    flake_issue.put()

    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(flake_issue, fetched_flake_issues[0])
    self.assertIsNotNone(fetched_flake_issues[0].last_updated_time)

  def testLuciProjectToMonorailProject(self):
    self.assertEqual('chromium',
                     FlakeIssue.GetMonorailProjectFromLuciProject('chromium'))
    self.assertIsNone(FlakeIssue.GetMonorailProjectFromLuciProject('NA'))
