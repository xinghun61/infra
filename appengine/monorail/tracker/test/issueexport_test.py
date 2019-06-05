# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the issueexport servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from mock import Mock, patch

from framework import permissions
from proto import tracker_pb2
from services import service_manager
from testing import testing_helpers
from testing import fake
from tracker import issueexport


class IssueExportTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        project=fake.ProjectService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        issue_star=fake.IssueStarService(),
    )
    self.cnxn = 'fake connection'
    self.project = self.services.project.TestAddProject('proj', project_id=789)
    self.servlet = issueexport.IssueExport(
        'req', 'res', services=self.services)
    self.jsonfeed = issueexport.IssueExportJSON(
        'req', 'res', services=self.services)
    self.mr = testing_helpers.MakeMonorailRequest(
        project=self.project, perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.mr.can = 1

  def testAssertBasePermission(self):
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, self.mr)
    self.mr.auth.user_pb.is_site_admin = True
    self.servlet.AssertBasePermission(self.mr)

  @patch('time.time')
  def testHandleRequest(self, mockTime):
    mockTime.return_value = 1234
    self.services.issue.GetAllIssuesInProject = Mock(return_value=[])
    self.services.issue.GetCommentsForIssues = Mock(return_value={})
    self.services.issue_star.LookupItemsStarrers = Mock(return_value={})
    self.services.user.LookupUserEmails = Mock(
        return_value={111: 'user1@test.com', 222: 'user2@test.com'})

    self.mr.project_name = self.project.project_name
    json_data = self.jsonfeed.HandleRequest(self.mr)

    self.assertEqual(json_data['metadata'],
                     {'version': 1, 'who': None, 'when': 1234,
                      'project': 'proj', 'start': 0, 'num': 100})
    self.assertEqual(json_data['issues'], [])
    self.assertItemsEqual(
        json_data['emails'], ['user1@test.com', 'user2@test.com'])

  # TODO(jojwang): test attachments, amendments, comment details
  def testMakeIssueJSON(self):
    config = self.services.config.GetProjectConfig(
        self.cnxn, 789)
    config.field_defs.extend(
        [tracker_pb2.FieldDef(
            field_id=1, field_name='UXReview',
            field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE),
         tracker_pb2.FieldDef(
             field_id=2, field_name='approvalsubfield',
             field_type=tracker_pb2.FieldTypes.STR_TYPE, approval_id=1),
         tracker_pb2.FieldDef(
             field_id=3, field_name='phasefield',
             field_type=tracker_pb2.FieldTypes.INT_TYPE, is_phase_field=True),
         tracker_pb2.FieldDef(
             field_id=4, field_name='normalfield',
             field_type=tracker_pb2.FieldTypes.STR_TYPE)
        ])
    self.services.config.StoreConfig(self.cnxn, config)

    phases = [tracker_pb2.Phase(phase_id=1, name='Phase1', rank=1),
              tracker_pb2.Phase(phase_id=2, name='Phase2', rank=2)]
    avs = [tracker_pb2.ApprovalValue(
        approval_id=1, status=tracker_pb2.ApprovalStatus.APPROVED,
        setter_id=111, set_on=7, approver_ids=[333, 444], phase_id=1)]
    fvs = [tracker_pb2.FieldValue(field_id=2, str_value='two'),
           tracker_pb2.FieldValue(field_id=3, int_value=3, phase_id=2),
           tracker_pb2.FieldValue(field_id=4, str_value='four')]
    labels = ['test', 'Type-FLT-Launch']

    issue = fake.MakeTestIssue(
        self.project.project_id, 1, 'summary', 'Open', 111, labels=labels,
        issue_id=78901, reporter_id=222, opened_timestamp=1,
        closed_timestamp=2, modified_timestamp=3, project_name='project',
        field_values=fvs, phases=phases, approval_values=avs)

    email_dict = {111: 'user1@test.com', 222: 'user2@test.com',
                  333: 'user3@test.com', 444: 'user4@test.com'}
    comment_list = [
        tracker_pb2.IssueComment(content='simple'),
        tracker_pb2.IssueComment(
            content='issue desc', is_description=True)]
    starrer_id_list = [222, 333]

    issue_JSON = self.jsonfeed._MakeIssueJSON(
        self.mr, issue, email_dict, comment_list, starrer_id_list)
    expected_JSON = {
        'local_id': 1,
        'reporter': 'user2@test.com',
        'summary': 'summary',
        'owner': 'user1@test.com',
        'status': 'Open',
        'cc': [],
        'labels': labels,
        'phases': [{'id': 1, 'name': 'Phase1', 'rank': 1},
                   {'id': 2, 'name': 'Phase2', 'rank': 2}],
        'fields': [
            {'field': 'approvalsubfield',
             'phase': None,
             'approval': 'UXReview',
             'str_value': 'two'},
            {'field': 'phasefield',
             'phase': 'Phase2',
             'int_value': 3},
            {'field': 'normalfield',
             'phase': None,
             'str_value': 'four'}],
        'approvals': [
            {'approval': 'UXReview',
             'status': 'APPROVED',
             'setter': 'user1@test.com',
             'set_on': 7,
             'approvers': ['user3@test.com', 'user4@test.com'],
             'phase': 'Phase1'}
        ],
        'starrers': ['user2@test.com', 'user3@test.com'],
        'comments': [
            {'content': 'simple',
             'timestamp': None,
             'amendments': [],
             'commenter': None,
             'attachments': [],
             'description_num': None},
            {'content': 'issue desc',
             'timestamp': None,
             'amendments': [],
             'commenter': None,
             'attachments': [],
             'description_num': '1'},
            ],
        'opened': 1,
        'modified': 3,
        'closed': 2,
    }

    self.assertEqual(expected_JSON, issue_JSON)
