# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from google.appengine.api import app_identity

from gae_libs.testcase import TestCase
from model.flake.flake_issue import FlakeIssue


class FlakeIssueTest(TestCase):

  def testCreate(self):
    monorail_project = 'chromium'
    issue_id = 123
    FlakeIssue.Create(
        monorail_project=monorail_project, issue_id=issue_id).put()

    flake_issue = FlakeIssue.Get(monorail_project, issue_id)

    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(flake_issue, fetched_flake_issues[0])
    self.assertIsNone(
        fetched_flake_issues[0].last_updated_time_by_flake_detection)
    self.assertEqual(monorail_project, flake_issue.monorail_project)
    self.assertEqual(issue_id, flake_issue.issue_id)
    self.assertIsNone(flake_issue.merge_destination_key)

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
        ('https://monorail-staging.appspot.com/p/chromium/issues/detail?'
         'id=12345'), FlakeIssue.GetLinkForIssue(monorail_project, issue_id))

  @mock.patch.object(
      app_identity, 'get_application_id', return_value='findit-for-me')
  def testGetLinkForProdIssue(self, _):
    monorail_project = 'chromium'
    issue_id = 12345
    self.assertEqual(
        'https://monorail-prod.appspot.com/p/chromium/issues/detail?id=12345',
        FlakeIssue.GetLinkForIssue(monorail_project, issue_id))

  def testGetMostUpdatedIssue(self):
    monorail_project = 'chromium'
    issue_id = 12345
    merge_issue_id = 67890

    merge_issue = FlakeIssue.Create(
        monorail_project=monorail_project, issue_id=merge_issue_id)
    merge_issue.put()

    flake_issue = FlakeIssue.Create(
        monorail_project=monorail_project, issue_id=issue_id)
    flake_issue.merge_destination_key = merge_issue.key
    flake_issue.put()

    self.assertEqual(merge_issue, flake_issue.GetMostUpdatedIssue())

  def testGetMostUpdatedIssueNoMergeKeyOnly(self):
    monorail_project = 'chromium'
    issue_id = 12345

    flake_issue = FlakeIssue.Create(
        monorail_project=monorail_project, issue_id=issue_id)
    flake_issue.put()

    self.assertEqual(flake_issue.key,
                     flake_issue.GetMostUpdatedIssue(key_only=True))

  def testUpdate(self):
    monorail_project = 'chromium'
    issue_id = 12345
    updated_time = datetime(2018, 12, 4, 0, 0, 0)
    status = 'Assigned'
    labels = ['Type-Bug', 'Pri-1']

    flake_issue = FlakeIssue.Create(
        monorail_project=monorail_project, issue_id=issue_id)
    flake_issue.put()

    flake_issue.Update(
        last_updated_time_in_monorail=updated_time,
        status=status,
        labels=labels)
    flake_issue = flake_issue.key.get()

    self.assertEqual(status, flake_issue.status)
    self.assertEqual(labels, flake_issue.labels)
    self.assertEqual(updated_time, flake_issue.last_updated_time_in_monorail)
