# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for notify_reasons.py."""

import unittest
import os

from google.appengine.api import taskqueue
from google.appengine.ext import testbed

from features import notify_reasons
from framework import emailfmt
from framework import framework_views
from framework import urls
from services import service_manager
from testing import fake


REPLY_NOT_ALLOWED = notify_reasons.REPLY_NOT_ALLOWED
REPLY_MAY_COMMENT = notify_reasons.REPLY_MAY_COMMENT
REPLY_MAY_UPDATE = notify_reasons.REPLY_MAY_UPDATE


class ComputeIssueChangeAddressPermListTest(unittest.TestCase):

  def setUp(self):
    self.users_by_id = {
        111L: framework_views.StuffUserView(111L, 'owner@example.com', True),
        222L: framework_views.StuffUserView(222L, 'member@example.com', True),
        999L: framework_views.StuffUserView(999L, 'visitor@example.com', True),
        }
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService())
    self.owner = self.services.user.TestAddUser('owner@example.com', 111L)
    self.member = self.services.user.TestAddUser('member@example.com', 222L)
    self.visitor = self.services.user.TestAddUser('visitor@example.com', 999L)
    self.project = self.services.project.TestAddProject(
        'proj', owner_ids=[111L], committer_ids=[222L])
    self.project.process_inbound_email = True
    self.issue = fake.MakeTestIssue(
        self.project.project_id, 1, 'summary', 'New', 111L)

  def testEmptyIDs(self):
    cnxn = 'fake cnxn'
    addr_perm_list = notify_reasons.ComputeIssueChangeAddressPermList(
        cnxn, [], self.project, self.issue, self.services, [], {})
    self.assertEqual([], addr_perm_list)

  def testRecipientIsMember(self):
    cnxn = 'fake cnxn'
    ids_to_consider = [111L, 222L, 999L]
    addr_perm_list = notify_reasons.ComputeIssueChangeAddressPermList(
        cnxn, ids_to_consider, self.project, self.issue, self.services, set(),
        self.users_by_id, pref_check_function=lambda *args: True)
    self.assertEqual(
        [(True, 'owner@example.com', self.owner, REPLY_MAY_UPDATE),
         (True, 'member@example.com', self.member, REPLY_MAY_UPDATE),
         (False, 'visitor@example.com', self.visitor, REPLY_MAY_COMMENT)],
        addr_perm_list)


class ComputeProjectAndIssueNotificationAddrListTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService())
    self.project = self.services.project.TestAddProject('project')
    self.services.user.TestAddUser('alice@gmail.com', 111L)
    self.services.user.TestAddUser('bob@gmail.com', 222L)
    self.services.user.TestAddUser('fred@gmail.com', 555L)

  def testNotifyAddress(self):
    # No mailing list or filter rules are defined
    addr_perm_list = notify_reasons.ComputeProjectNotificationAddrList(
        self.project, True, set())
    self.assertListEqual([], addr_perm_list)

    # Only mailing list is notified.
    self.project.issue_notify_address = 'mailing-list@domain.com'
    addr_perm_list = notify_reasons.ComputeProjectNotificationAddrList(
        self.project, True, set())
    self.assertListEqual(
        [(False, 'mailing-list@domain.com', None, REPLY_NOT_ALLOWED)],
        addr_perm_list)

    # No one is notified because mailing list was already notified.
    omit_addrs = {'mailing-list@domain.com'}
    addr_perm_list = notify_reasons.ComputeProjectNotificationAddrList(
        self.project, False, omit_addrs)
    self.assertListEqual([], addr_perm_list)

    # No one is notified because anon users cannot view.
    addr_perm_list = notify_reasons.ComputeProjectNotificationAddrList(
        self.project, False, set())
    self.assertListEqual([], addr_perm_list)

  def testFilterRuleNotifyAddresses(self):
    issue = fake.MakeTestIssue(
        self.project.project_id, 1, 'summary', 'New', 555L)
    issue.derived_notify_addrs.extend(['notify@domain.com'])

    addr_perm_list = notify_reasons.ComputeIssueNotificationAddrList(
        issue, set())
    self.assertListEqual(
        [(False, 'notify@domain.com', None, REPLY_NOT_ALLOWED)],
        addr_perm_list)

    # Also-notify addresses can be omitted (e.g., if it is the same as
    # the email address of the user who made the change).
    addr_perm_list = notify_reasons.ComputeIssueNotificationAddrList(
        issue, {'notify@domain.com'})
    self.assertListEqual([], addr_perm_list)

