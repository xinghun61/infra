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
    self.local_id_1 = self.services.issue.CreateIssue(
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

  def testPairDerivedValuesWithRuleExplanations_Nothing(self):
    proposed_issue = tracker_pb2.Issue()  # No derived values.
    traces = {}
    derived_users_by_id = {}
    actual = issuepresubmit.PairDerivedValuesWithRuleExplanations(
        proposed_issue, traces, derived_users_by_id)
    (derived_labels_and_why, derived_owner_and_why,
     derived_cc_and_why, warnings_and_why) = actual
    self.assertEqual([], derived_labels_and_why)
    self.assertEqual([], derived_owner_and_why)
    self.assertEqual([], derived_cc_and_why)
    self.assertEqual([], warnings_and_why)

  def testPairDerivedValuesWithRuleExplanations_SomeValues(self):
    proposed_issue = tracker_pb2.Issue(
        derived_owner_id=111L, derived_cc_ids=[222L, 333L],
        derived_labels=['aaa', 'zzz'], warnings=['Watch out'])
    traces = {
        (tracker_pb2.FieldID.OWNER, 111L): 'explain 1',
        (tracker_pb2.FieldID.CC, 222L): 'explain 2',
        (tracker_pb2.FieldID.CC, 333L): 'explain 3',
        (tracker_pb2.FieldID.LABELS, 'aaa'): 'explain 4',
        (tracker_pb2.FieldID.WARNING, 'Watch out'): 'explain 6',
        # There can be extra traces that are not used.
        (tracker_pb2.FieldID.LABELS, 'bbb'): 'explain 5',
        # If there is no trace for some derived value, why is None.
        }
    derived_users_by_id = {
      111L: testing_helpers.Blank(email='one@example.com'),
      222L: testing_helpers.Blank(email='two@example.com'),
      333L: testing_helpers.Blank(email='three@example.com'),
      }
    actual = issuepresubmit.PairDerivedValuesWithRuleExplanations(
        proposed_issue, traces, derived_users_by_id)
    (derived_labels_and_why, derived_owner_and_why,
     derived_cc_and_why, warnings_and_why) = actual
    self.assertEqual([
        {'value': 'aaa', 'why': 'explain 4'},
        {'value': 'zzz', 'why': None},
        ], derived_labels_and_why)
    self.assertEqual([
        {'value': 'one@example.com', 'why': 'explain 1'},
        ], derived_owner_and_why)
    self.assertEqual([
        {'value': 'two@example.com', 'why': 'explain 2'},
        {'value': 'three@example.com', 'why': 'explain 3'},
        ], derived_cc_and_why)
    self.assertEqual([
        {'value': 'Watch out', 'why': 'explain 6'},
        ], warnings_and_why)
