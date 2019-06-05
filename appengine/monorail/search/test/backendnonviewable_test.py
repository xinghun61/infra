# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.search.backendnonviewable."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest
import mox

from google.appengine.api import memcache
from google.appengine.ext import testbed

from framework import permissions
from search import backendnonviewable
from services import service_manager
from testing import fake
from testing import testing_helpers


class BackendNonviewableTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        )
    self.project = self.services.project.TestAddProject(
      'proj', project_id=789)
    self.mr = testing_helpers.MakeMonorailRequest()
    self.mr.specified_project_id = 789
    self.mr.shard_id = 2
    self.mr.invalidation_timestep = 12345

    self.servlet = backendnonviewable.BackendNonviewable(
        'req', 'res', services=self.services)

    self.mox = mox.Mox()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testHandleRequest(self):
    pass  # TODO(jrobbins): fill in this test.

  def testGetNonviewableIIDs_OwnerOrAdmin(self):
    """Check the special case for users who are never restricted."""
    perms = permissions.OWNER_ACTIVE_PERMISSIONSET
    nonviewable_iids = self.servlet.GetNonviewableIIDs(
      self.mr.cnxn, self.mr.auth.user_pb, {111}, self.project, perms, 2)
    self.assertEqual([], nonviewable_iids)

  def testGetNonviewableIIDs_RegularUser(self):
    pass  # TODO(jrobbins)

  def testGetNonviewableIIDs_Anon(self):
    pass  # TODO(jrobbins)

  def testGetAtRiskIIDs_NothingEverAtRisk(self):
    """Handle the case where the site has no restriction labels."""
    fake_restriction_label_rows = []
    fake_restriction_label_ids = []
    fake_at_risk_iids = []
    self.mox.StubOutWithMock(self.services.config, 'GetLabelDefRowsAnyProject')
    self.services.config.GetLabelDefRowsAnyProject(
        self.mr.cnxn, where=[('LOWER(label) LIKE %s', ['restrict-view-%'])]
        ).AndReturn(fake_restriction_label_rows)
    self.mox.StubOutWithMock(self.services.issue, 'GetIIDsByLabelIDs')
    self.services.issue.GetIIDsByLabelIDs(
        self.mr.cnxn, fake_restriction_label_ids, 789, 2
        ).AndReturn(fake_at_risk_iids)
    self.mox.ReplayAll()

    at_risk_iids = self.servlet.GetAtRiskIIDs(
        self.mr.cnxn, self.mr.auth.user_pb, self.mr.auth.effective_ids,
        self.project, self.mr.perms, self.mr.shard_id)
    self.mox.VerifyAll()
    self.assertEqual([], at_risk_iids)

  def testGetAtRiskIIDs_NoIssuesAtRiskRightNow(self):
    """Handle the case where the project has no restricted issues."""
    fake_restriction_label_rows = [
        (123, 789, 1, 'Restrict-View-A', 'doc', False),
        (234, 789, 2, 'Restrict-View-B', 'doc', False),
        ]
    fake_restriction_label_ids = [123, 234]
    fake_at_risk_iids = []
    self.mox.StubOutWithMock(self.services.config, 'GetLabelDefRowsAnyProject')
    self.services.config.GetLabelDefRowsAnyProject(
        self.mr.cnxn, where=[('LOWER(label) LIKE %s', ['restrict-view-%'])]
        ).AndReturn(fake_restriction_label_rows)
    self.mox.StubOutWithMock(self.services.issue, 'GetIIDsByLabelIDs')
    self.services.issue.GetIIDsByLabelIDs(
        self.mr.cnxn, fake_restriction_label_ids, 789, 2
        ).AndReturn(fake_at_risk_iids)
    self.mox.ReplayAll()

    at_risk_iids = self.servlet.GetAtRiskIIDs(
        self.mr.cnxn, self.mr.auth.user_pb, self.mr.auth.effective_ids,
        self.project, self.mr.perms, self.mr.shard_id)
    self.mox.VerifyAll()
    self.assertEqual([], at_risk_iids)

  def testGetAtRiskIIDs_SomeAtRisk(self):
    """Handle the case where the project has some restricted issues."""
    fake_restriction_label_rows = [
        (123, 789, 1, 'Restrict-View-A', 'doc', False),
        (234, 789, 2, 'Restrict-View-B', 'doc', False),
        ]
    fake_restriction_label_ids = [123, 234]
    fake_at_risk_iids = [432, 543]
    self.mox.StubOutWithMock(self.services.config, 'GetLabelDefRowsAnyProject')
    self.services.config.GetLabelDefRowsAnyProject(
      self.mr.cnxn, where=[('LOWER(label) LIKE %s', ['restrict-view-%'])]
      ).AndReturn(fake_restriction_label_rows)
    self.mox.StubOutWithMock(self.services.issue, 'GetIIDsByLabelIDs')
    self.services.issue.GetIIDsByLabelIDs(
      self.mr.cnxn, fake_restriction_label_ids, 789, 2
      ).AndReturn(fake_at_risk_iids)
    self.mox.ReplayAll()

    at_risk_iids = self.servlet.GetAtRiskIIDs(
        self.mr.cnxn, self.mr.auth.user_pb, self.mr.auth.effective_ids,
        self.project, self.mr.perms, self.mr.shard_id)
    self.mox.VerifyAll()
    self.assertEqual([432, 543], at_risk_iids)

  def testGetViewableIIDs_Anon(self):
    """Anon users are never participants in any issues."""
    ok_iids = self.servlet.GetViewableIIDs(
      self.mr.cnxn, set(), 789, 2)
    self.assertEqual([], ok_iids)

  def testGetViewableIIDs_NoIssues(self):
    """This visitor does not participate in any issues."""
    self.mox.StubOutWithMock(self.services.issue, 'GetIIDsByParticipant')
    self.services.issue.GetIIDsByParticipant(
      self.mr.cnxn, {111}, [789], 2).AndReturn([])
    self.mox.ReplayAll()

    ok_iids = self.servlet.GetViewableIIDs(
      self.mr.cnxn, {111}, 789, 2)
    self.mox.VerifyAll()
    self.assertEqual([], ok_iids)

  def testGetViewableIIDs_SomeIssues(self):
    """This visitor  participates in some issues."""
    self.mox.StubOutWithMock(self.services.issue, 'GetIIDsByParticipant')
    self.services.issue.GetIIDsByParticipant(
      self.mr.cnxn, {111}, [789], 2).AndReturn([543, 654])
    self.mox.ReplayAll()

    ok_iids = self.servlet.GetViewableIIDs(
      self.mr.cnxn, {111}, 789, 2)
    self.mox.VerifyAll()
    self.assertEqual([543, 654], ok_iids)
