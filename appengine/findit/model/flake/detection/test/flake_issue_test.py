# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from google.appengine.api import app_identity

from gae_libs.testcase import TestCase
from model.flake.detection.flake_issue import FlakeIssue


class FlakeIssueTest(TestCase):

  def testCreate(self):
    monorail_project = 'chromium'
    issue_id = 123
    flake_issue = FlakeIssue.Create(
        monorail_project=monorail_project, issue_id=issue_id)

    flake_issue.put()

    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(flake_issue, fetched_flake_issues[0])
    self.assertIsNone(fetched_flake_issues[0].last_updated_time)

  def testLuciProjectToMonorailProject(self):
    self.assertEqual('chromium',
                     FlakeIssue.GetMonorailProjectFromLuciProject('chromium'))
    self.assertIsNone(FlakeIssue.GetMonorailProjectFromLuciProject('NA'))

  @mock.patch.object(
      app_identity, 'get_application_id', return_value='findit-for-me-staging')
  def testGetLinkForStagingIssue(self, _):
    monorail_project = 'chromium'
    issue_id = 12345
    self.assertEqual(
        'https://monorail-staging.appspot.com/p/chromium/issues/detail?id=12345',  # pylint: disable=line-too-long
        FlakeIssue.GetLinkForIssue(monorail_project, issue_id))

  @mock.patch.object(
      app_identity, 'get_application_id', return_value='findit-for-me')
  def testGetLinkForProdIssue(self, _):
    monorail_project = 'chromium'
    issue_id = 12345
    self.assertEqual(
        'https://monorail-prod.appspot.com/p/chromium/issues/detail?id=12345',
        FlakeIssue.GetLinkForIssue(monorail_project, issue_id))
