# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the service_manager module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from features import autolink
from services import cachemanager_svc
from services import config_svc
from services import features_svc
from services import issue_svc
from services import service_manager
from services import project_svc
from services import star_svc
from services import user_svc
from services import usergroup_svc


class ServiceManagerTest(unittest.TestCase):

  def testSetUpServices(self):
    svcs = service_manager.set_up_services()
    self.assertIsInstance(svcs, service_manager.Services)
    self.assertIsInstance(svcs.autolink, autolink.Autolink)
    self.assertIsInstance(svcs.cache_manager, cachemanager_svc.CacheManager)
    self.assertIsInstance(svcs.user, user_svc.UserService)
    self.assertIsInstance(svcs.user_star, star_svc.UserStarService)
    self.assertIsInstance(svcs.project_star, star_svc.ProjectStarService)
    self.assertIsInstance(svcs.issue_star, star_svc.IssueStarService)
    self.assertIsInstance(svcs.project, project_svc.ProjectService)
    self.assertIsInstance(svcs.usergroup, usergroup_svc.UserGroupService)
    self.assertIsInstance(svcs.config, config_svc.ConfigService)
    self.assertIsInstance(svcs.issue, issue_svc.IssueService)
    self.assertIsInstance(svcs.features, features_svc.FeaturesService)

    # Calling it again should give the same object
    svcs2 = service_manager.set_up_services()
    self.assertTrue(svcs is svcs2)
