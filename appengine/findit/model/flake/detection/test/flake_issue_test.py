# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

from gae_libs.testcase import TestCase

from model.flake.detection.flake_issue import FlakeIssue


class FlakeIssueTest(TestCase):

  def testFromMonorailIssue(self):
    issue = mock.Mock()
    issue.id = '123'
    issue.project_id = 'chromium'
    issue.updated = datetime.datetime(2018, 1, 1)

    flake_issue = FlakeIssue()
    self.assertIsNone(flake_issue.issue_id)
    self.assertIsNone(flake_issue.last_updated_time)

    flake_issue.FromMonorailIssue(issue)
    self.assertEqual(flake_issue.issue_id, issue.id)
    self.assertIsNone(flake_issue.last_updated_time)
