# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the reap module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

import mock
import mox

from mock import Mock

from framework import reap
from framework import sql
from proto import project_pb2
from services import service_manager
from services import template_svc
from testing import fake
from testing import testing_helpers


class ReapTest(unittest.TestCase):

  def setUp(self):
    self.project_service = fake.ProjectService()
    self.issue_service = fake.IssueService()
    self.issue_star_service = fake.IssueStarService()
    self.config_service = fake.ConfigService()
    self.features_service = fake.FeaturesService()
    self.project_star_service = fake.ProjectStarService()
    self.services = service_manager.Services(
        project=self.project_service,
        issue=self.issue_service,
        issue_star=self.issue_star_service,
        config=self.config_service,
        features=self.features_service,
        project_star=self.project_star_service,
        template=Mock(spec=template_svc.TemplateService),
        user=fake.UserService(),
        usergroup=fake.UserGroupService())

    self.proj1_id = 1001
    self.proj1_issue_id = 111
    self.proj1 = self.project_service.TestAddProject(
        name='proj1', project_id=self.proj1_id)
    self.proj2_id = 1002
    self.proj2_issue_id = 112
    self.proj2 = self.project_service.TestAddProject(
        name='proj2', project_id=self.proj2_id)

    self.mox = mox.Mox()
    self.cnxn = self.mox.CreateMock(sql.MonorailConnection)
    self.project_service.project_tbl = self.mox.CreateMock(sql.SQLTableManager)
    self.issue_service.issue_tbl = self.mox.CreateMock(sql.SQLTableManager)

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def setUpMarkDoomedProjects(self):
    self.project_service.project_tbl.Select(
        self.cnxn, cols=['project_id'], limit=1000, state='archived',
        where=mox.IgnoreArg()).AndReturn([[self.proj1_id]])

  def testMarkDoomedProjects(self):
    self.setUpMarkDoomedProjects()
    reaper = reap.Reap('req', 'resp', services=self.services)

    self.mox.ReplayAll()
    doomed_project_ids = reaper._MarkDoomedProjects(self.cnxn)
    self.mox.VerifyAll()

    self.assertEquals([self.proj1_id], doomed_project_ids)
    self.assertEquals(project_pb2.ProjectState.DELETABLE, self.proj1.state)
    self.assertEquals('DELETABLE_%s' % self.proj1_id , self.proj1.project_name)

  def setUpExpungeParts(self):
    self.project_service.project_tbl.Select(
        self.cnxn, cols=['project_id'], limit=100,
        state='deletable').AndReturn([[self.proj1_id], [self.proj2_id]])
    self.issue_service.issue_tbl.Select(
        self.cnxn, cols=['id'], limit=1000,
        project_id=self.proj1_id).AndReturn([[self.proj1_issue_id]])
    self.issue_service.issue_tbl.Select(
        self.cnxn, cols=['id'], limit=1000,
        project_id=self.proj2_id).AndReturn([[self.proj2_issue_id]])

  def testExpungeDeletableProjects(self):
    self.setUpExpungeParts()
    reaper = reap.Reap('req', 'resp', services=self.services)

    self.mox.ReplayAll()
    expunged_project_ids = reaper._ExpungeDeletableProjects(self.cnxn)
    self.mox.VerifyAll()

    self.assertEquals([self.proj1_id, self.proj2_id], expunged_project_ids)
    # Verify all expected expunge methods were called.
    self.assertEquals([self.proj1_issue_id, self.proj2_issue_id],
                      self.services.issue_star.expunged_item_ids)
    self.assertEquals([self.proj1_issue_id, self.proj2_issue_id],
                      self.services.issue.expunged_issues)
    self.assertEquals([self.proj1_id, self.proj2_id],
                      self.services.config.expunged_configs)
    self.assertEquals([self.proj1_id, self.proj2_id],
                      self.services.features.expunged_saved_queries)
    self.assertEquals([self.proj1_id, self.proj2_id],
                      self.services.features.expunged_filter_rules)
    self.assertEquals([self.proj1_id, self.proj2_id],
                      self.services.issue.expunged_former_locations)
    self.assertEquals([self.proj1_id, self.proj2_id],
                      self.services.issue.expunged_local_ids)
    self.assertEquals([self.proj1_id, self.proj2_id],
                      self.services.features.expunged_quick_edit)
    self.assertEquals([self.proj1_id, self.proj2_id],
                      self.services.project_star.expunged_item_ids)
    self.assertEquals(0, len(self.services.project.test_projects))
    self.services.template.ExpungeProjectTemplates.assert_has_calls([
        mock.call(self.cnxn, 1001),
        mock.call(self.cnxn, 1002)])
