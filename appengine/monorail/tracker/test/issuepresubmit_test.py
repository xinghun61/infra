# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.tracker.issuepresubmit."""

import unittest

from framework import permissions
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import issuepresubmit
from tracker import tracker_bizobj
from tracker import tracker_helpers


class IssuePresubmitTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        spam=fake.SpamService())
    self.proj = self.services.project.TestAddProject('proj', project_id=789)
    self.cnxn = 'fake cnxn'
    self.servlet = issuepresubmit.IssuePresubmitJSON(
        'req', 'res', services=self.services)
    self.local_id_1, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services,
        789, 'summary', 'status', 111L, [], [], [], [], 111L,
        'The screen is just dark when I press power on')

  def testAssertBasePermission_NormalNewIssue(self):
    mr = testing_helpers.MakeMonorailRequest(
        project=self.proj,
        perms=permissions.EMPTY_PERMISSIONSET)
    # Note: mr.issue_id is None
    self.servlet.AssertBasePermission(mr)

  def testAssertBasePermission_NormalExistingIssue(self):
    mr = testing_helpers.MakeMonorailRequest(
        project=self.proj,
        perms=permissions.USER_PERMISSIONSET)
    mr.local_id = self.local_id_1
    self.servlet.AssertBasePermission(mr)

  def testAssertBasePermission_NoPermsExistingIssue(self):
    mr = testing_helpers.MakeMonorailRequest(
        project=self.proj,
        perms=permissions.EMPTY_PERMISSIONSET)
    mr.local_id = self.local_id_1
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)

  def testMakeProposedIssue_NoCustomFields(self):
    parsed_users = tracker_helpers.ParsedUsers('', 0, [], [], [], [])
    parsed_fields = tracker_helpers.ParsedFields({}, {}, [])
    parsed = tracker_helpers.ParsedIssue(
        'sum', 'comment', False, 'New', parsed_users, ['a', 'b'],
        [], [], parsed_fields, 'template', [], [],[], [], [])
    mr = testing_helpers.MakeMonorailRequest(
        project=self.proj,
        perms=permissions.USER_PERMISSIONSET)
    mr.local_id = self.local_id_1
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    component_ids = []
    proposed_issue = self.servlet.MakeProposedIssue(
        mr, None, parsed, config, component_ids)
    self.assertEqual(['a', 'b'], proposed_issue.labels)

  def testMakeProposedIssue_SomeCustomFields(self):
    fd = tracker_pb2.FieldDef(
        field_id=123, project_id=self.proj.project_id,
        field_name='Size', field_type=tracker_pb2.FieldTypes.ENUM_TYPE)
    parsed_users = tracker_helpers.ParsedUsers('', 0, [], [], [], [])
    parsed_fields = tracker_helpers.ParsedFields(
      {123: ['Small']}, {}, [])
    parsed = tracker_helpers.ParsedIssue(
        'sum', 'comment', False, 'New', parsed_users, ['a', 'b'],
        [], [], parsed_fields, 'template', [], [],[], [], [])
    mr = testing_helpers.MakeMonorailRequest(
        project=self.proj,
        perms=permissions.USER_PERMISSIONSET)
    mr.local_id = self.local_id_1
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.field_defs = [fd]
    config.well_known_labels = [
      tracker_pb2.LabelDef(label='Size-Small'),
      tracker_pb2.LabelDef(label='Size-Medium'),
      tracker_pb2.LabelDef(label='Size-Large'),
      ]
    component_ids = []
    proposed_issue = self.servlet.MakeProposedIssue(
        mr, None, parsed, config, component_ids)
    self.assertEqual(['a', 'b', 'Size-Small'], proposed_issue.labels)

  def testMakeProposedIssue_CountsFromExistingIssue(self):
    parsed_users = tracker_helpers.ParsedUsers('', 0, [], [], [], [])
    parsed_fields = tracker_helpers.ParsedFields({}, {}, [])
    parsed = tracker_helpers.ParsedIssue(
        'sum', 'comment', False, 'New', parsed_users, ['a', 'b'],
        [], [], parsed_fields, 'template', [], [],[], [], [])
    mr = testing_helpers.MakeMonorailRequest(
        project=self.proj,
        perms=permissions.USER_PERMISSIONSET)
    mr.local_id = self.local_id_1
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    component_ids = []
    existing_issue = tracker_pb2.Issue(
      attachment_count=123, star_count=456)
    proposed_issue = self.servlet.MakeProposedIssue(
        mr, existing_issue, parsed, config, component_ids)
    self.assertEqual(123, proposed_issue.attachment_count)
    self.assertEqual(456, proposed_issue.star_count)
