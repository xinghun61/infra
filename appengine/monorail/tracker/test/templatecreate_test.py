# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit test for Template creation servlet."""

import unittest

import settings

from framework import permissions
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import templatecreate
from tracker import tracker_bizobj
from tracker import tracker_views
from proto import tracker_pb2


class TemplateCreateTest(unittest.TestCase):
  """Tests for the TemplateCreate servlet."""

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.mr = testing_helpers.MakeMonorailRequest()
    self.services = service_manager.Services(project=fake.ProjectService(),
                                             config=fake.ConfigService(),
                                             user=fake.UserService())
    self.servlet = templatecreate.TemplateCreate('req', 'res',
                                               services=self.services)

  def testAssertBasePermission(self):
    # Anon users can never do it
    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

    # Project owner can do it.
    self.mr.perms = permissions.OWNER_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)

    # Project member cannot do it
    self.mr.perms = permissions.COMMITTER_ACTIVE_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)
    self.mr.perms = permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

  def testGatherPageData(self):
    fd = tracker_bizobj.MakeFieldDef(
        1, self.mr.project_id, 'StringFieldName',
        tracker_pb2.FieldTypes.STR_TYPE, None, '', False,
        False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'some approval thing', False)
    config = self.services.config.GetProjectConfig(
        self.mr.cnxn, self.mr.project_id)
    config.field_defs.append(fd)
    self.services.config.StoreConfig(self.cnxn, config)
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.PROCESS_TAB_TEMPLATES,
                     page_data['admin_tab_mode'])
    fv = tracker_views.MakeFieldValueView(fd, config, [], [], [], {})
    self.assertEqual(page_data['fields'][0].field_name, fv.field_name)

  def testProcessFormData(self):
    post_data = fake.PostData()
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertTrue('/adminTemplates' in url)
