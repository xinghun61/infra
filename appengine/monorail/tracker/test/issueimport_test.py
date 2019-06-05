# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the issueimport servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from framework import permissions
from services import service_manager
from testing import testing_helpers
from tracker import issueimport
from proto import tracker_pb2


class IssueExportTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services()
    self.servlet = issueimport.IssueImport(
        'req', 'res', services=self.services)
    self.event_log = None

  def testAssertBasePermission(self):
    """Only site admins can import issues."""
    mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)
    mr.auth.user_pb.is_site_admin = True
    self.servlet.AssertBasePermission(mr)

  def testParseComment(self):
    """Test a Comment JSON is correctly parsed."""
    users_id_dict = {'adam@test.com': 111}
    json = {
        'timestamp': 123,
        'commenter': 'adam@test.com',
        'content': 'so basically, what I was thinkig of',
        'amendments': [],
        'attachments': [],
        'description_num': None,
        }
    comment = self.servlet._ParseComment(
        12, users_id_dict, json, self.event_log)
    self.assertEqual(
        comment, tracker_pb2.IssueComment(
            project_id=12, timestamp=123, user_id=111,
            content='so basically, what I was thinkig of'))

    json_desc = {
        'timestamp': 223,
        'commenter': 'adam@test.com',
        'content': 'I cant believe youve done this',
        'description_num': '2',
        'amendments': [],
        'attachments': [],
    }
    desc_comment = self.servlet._ParseComment(
        12, users_id_dict, json_desc, self.event_log)
    self.assertEqual(
        desc_comment, tracker_pb2.IssueComment(
            project_id=12, timestamp=223, user_id=111,
            content='I cant believe youve done this',
            is_description=True))
