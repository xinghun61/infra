# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for monorail.search.search_helpers."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mox
import unittest

from search import search_helpers

from google.appengine.ext import testbed
from framework import permissions
from framework import sql
from proto import user_pb2
from services import chart_svc
from services import service_manager
from testing import fake


def MakeChartService(my_mox, config):
  chart_service = chart_svc.ChartService(config)
  for table_var in ['issuesnapshot_tbl', 'labeldef_tbl']:
    setattr(chart_service, table_var, my_mox.CreateMock(sql.SQLTableManager))
  return chart_service


class SearchHelpersTest(unittest.TestCase):
  """Tests for functions in search_helpers.

  Also covered by search.backendnonviewable.GetAtRiskIIDs cases.
  """

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.mox = mox.Mox()
    self.cnxn = self.mox.CreateMock(sql.MonorailConnection)
    self.services = service_manager.Services()
    self.services.chart = MakeChartService(self.mox, self.services.config)
    self.config_service = fake.ConfigService()
    self.user = user_pb2.User()

  def testGetPersonalAtRiskLabelIDs_ReadOnly(self):
    """Test returns risky IDs a read-only user cannot access."""
    self.mox.StubOutWithMock(self.config_service, 'GetLabelDefRowsAnyProject')
    self.config_service.GetLabelDefRowsAnyProject(
      self.cnxn, where=[('LOWER(label) LIKE %s', ['restrict-view-%'])]
    ).AndReturn([
      (123, 789, 0, 'Restrict-View-Google', 'docstring', 0),
      (124, 789, 0, 'Restrict-View-SecurityTeam', 'docstring', 0),
    ])

    self.mox.ReplayAll()
    ids = search_helpers.GetPersonalAtRiskLabelIDs(
      self.cnxn,
      self.user,
      self.config_service,
      effective_ids=[10L, 20L],
      project=fake.Project(project_id=789),
      perms=permissions.READ_ONLY_PERMISSIONSET)
    self.mox.VerifyAll()

    self.assertEqual(ids, [123, 124])

  def testGetPersonalAtRiskLabelIDs_LoggedInUser(self):
    """Test returns restricted label IDs a logged in user cannot access."""
    self.mox.StubOutWithMock(self.config_service, 'GetLabelDefRowsAnyProject')
    self.config_service.GetLabelDefRowsAnyProject(
      self.cnxn, where=[('LOWER(label) LIKE %s', ['restrict-view-%'])]
    ).AndReturn([
      (123, 789, 0, 'Restrict-View-Google', 'docstring', 0),
      (124, 789, 0, 'Restrict-View-SecurityTeam', 'docstring', 0),
    ])

    self.mox.ReplayAll()
    ids = search_helpers.GetPersonalAtRiskLabelIDs(
      self.cnxn,
      self.user,
      self.config_service,
      effective_ids=[10L, 20L],
      project=fake.Project(project_id=789),
      perms=permissions.USER_PERMISSIONSET)
    self.mox.VerifyAll()

    self.assertEqual(ids, [123, 124])

  def testGetPersonalAtRiskLabelIDs_UserWithRVG(self):
    """Test returns restricted label IDs a logged in user cannot access."""
    self.mox.StubOutWithMock(self.config_service, 'GetLabelDefRowsAnyProject')
    self.config_service.GetLabelDefRowsAnyProject(
      self.cnxn, where=[('LOWER(label) LIKE %s', ['restrict-view-%'])]
    ).AndReturn([
      (123, 789, 0, 'Restrict-View-Google', 'docstring', 0),
      (124, 789, 0, 'Restrict-View-SecurityTeam', 'docstring', 0),
    ])

    self.mox.ReplayAll()
    perms = permissions.PermissionSet(['Google'])
    ids = search_helpers.GetPersonalAtRiskLabelIDs(
      self.cnxn,
      self.user,
      self.config_service,
      effective_ids=[10L, 20L],
      project=fake.Project(project_id=789),
      perms=perms)
    self.mox.VerifyAll()

    self.assertEqual(ids, [124])

  def testGetPersonalAtRiskLabelIDs_Admin(self):
    """Test returns nothing for an admin (who can view everything)."""
    self.user.is_site_admin = True
    self.mox.ReplayAll()
    ids = search_helpers.GetPersonalAtRiskLabelIDs(
      self.cnxn,
      self.user,
      self.config_service,
      effective_ids=[10L, 20L],
      project=fake.Project(project_id=789),
      perms=permissions.ADMIN_PERMISSIONSET)
    self.mox.VerifyAll()

    self.assertEqual(ids, [])
