# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the projectexport servlet."""

import unittest

from mock import Mock, patch

from framework import permissions
from project import projectexport
from proto import tracker_pb2
from services import service_manager
from services.template_svc import TemplateService
from testing import fake
from testing import testing_helpers


class ProjectExportTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services()
    self.servlet = projectexport.ProjectExport(
        'req', 'res', services=self.services)

  def testAssertBasePermission(self):
    mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)
    mr.auth.user_pb.is_site_admin = True
    self.servlet.AssertBasePermission(mr)


class ProjectExportJSONTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        project=fake.ProjectService(),
        user=fake.UserService(),
        template=Mock(spec=TemplateService))
    self.servlet = projectexport.ProjectExportJSON(
        'req', 'res', services=self.services)
    self.project = fake.Project(project_id=789)
    self.mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.mr.auth.user_pb.is_site_admin = True
    self.mr.project = self.project

  @patch('time.time')
  def testHandleRequest_Normal(self, mockTime):
    mockTime.return_value = 123456789
    self.services.project.GetProject = Mock(return_value=self.project)
    test_config = fake.MakeTestConfig(project_id=789, labels=[], statuses=[])
    self.services.config.GetProjectConfig = Mock(return_value=test_config)
    test_templates = testing_helpers.DefaultTemplates()
    self.services.template.GetProjectTemplates = Mock(
        return_value=tracker_pb2.TemplateSet(templates=test_templates))
    self.services.config.UsersInvolvedInConfig = Mock(return_value=[111L])

    json_data = self.servlet.HandleRequest(self.mr)

    expected = {
      'project': {
        'committers': [],
        'owners': [],
        'recent_activity': 0,
        'name': 'proj',
        'contributors': [],
        'perms': [],
        'attachment_quota': None,
        'process_inbound_email': False,
        'revision_url_format': None,
        'summary': '',
        'access': 'ANYONE',
        'state': 'LIVE',
        'read_only_reason': None,
        'only_owners_remove_restrictions': False,
        'only_owners_see_contributors': False,
        'attachment_bytes': 0,
        'issue_notify_address': None,
        'description': ''
      },
      'config': {
        'templates': [{
          'status': 'Accepted',
          'members_only': True,
          'labels': [],
          'summary_must_be_edited': True,
          'owner': None,
          'owner_defaults_to_member': True,
          'component_required': False,
          'name': 'Defect report from developer',
          'summary': 'Enter one-line summary',
          'content': 'What steps will reproduce the problem?\n1. \n2. \n3. \n'
            '\n'
            'What is the expected output?\n\n\nWhat do you see instead?\n'
            '\n\n'
            'Please use labels and text to provide additional information.\n',
          'admins': []
        }, {
          'status': 'New',
          'members_only': False,
          'labels': [],
          'summary_must_be_edited': True,
          'owner': None,
          'owner_defaults_to_member': True,
          'component_required': False,
          'name': 'Defect report from user',
          'summary': 'Enter one-line summary', 'content': 'What steps will '
            'reproduce the problem?\n1. \n2. \n3. \n\nWhat is the expected '
            'output?\n\n\nWhat do you see instead?\n\n\nWhat version of the '
            'product are you using? On what operating system?\n\n\nPlease '
            'provide any additional information below.\n',
          'admins': []
        }],
        'labels': [],
        'statuses_offer_merge': ['Duplicate'],
        'exclusive_label_prefixes': ['Type', 'Priority', 'Milestone'],
        'only_known_values': False,
        'statuses': [],
        'list_spec': '',
        'developer_template': 0,
        'user_template': 0,
        'grid_y': '',
        'grid_x': '',
        'components': [],
        'list_cols': 'ID Type Status Priority Milestone Owner Summary'
      },
      'emails': [None],
      'metadata': {
        'version': 1,
        'when': 123456789,
        'who': None,
      }
    }
    self.assertDictEqual(expected, json_data)
    self.services.template.GetProjectTemplates.assert_called_once_with(
        self.mr.cnxn, 789)
    self.services.config.UsersInvolvedInConfig.assert_called_once_with(
        test_config, test_templates)
