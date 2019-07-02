# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the WorkEnv class."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import sys
import unittest
import mock

from google.appengine.api import memcache
from google.appengine.ext import testbed

import settings
from businesslogic import work_env
from features import filterrules_helpers
from framework import exceptions
from framework import framework_constants
from framework import framework_views
from framework import permissions
from features import send_notifications
from proto import project_pb2
from proto import tracker_pb2
from proto import user_pb2
from services import config_svc
from services import features_svc
from services import issue_svc
from services import project_svc
from services import user_svc
from services import usergroup_svc
from services import service_manager
from services import spam_svc
from services import star_svc
from services import template_svc
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj


class WorkEnvTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake connection'
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        project=fake.ProjectService(),
        issue_star=fake.IssueStarService(),
        project_star=fake.ProjectStarService(),
        user_star=fake.UserStarService(),
        hotlist_star=fake.HotlistStarService(),
        features=fake.FeaturesService(),
        usergroup=fake.UserGroupService(),
        template=mock.Mock(spec=template_svc.TemplateService),
        spam=fake.SpamService())
    self.project = self.services.project.TestAddProject(
        'proj', project_id=789, committer_ids=[111])
    self.admin_user = self.services.user.TestAddUser(
        'admin@example.com', 444)
    self.admin_user.is_site_admin = True
    self.services.user.TestAddUser('user_111@example.com', 111)
    self.services.user.TestAddUser('user_222@example.com', 222)
    self.services.user.TestAddUser('user_333@example.com', 333)
    self.mr = testing_helpers.MakeMonorailRequest(project=self.project)
    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET

    self.work_env = work_env.WorkEnv(
      self.mr, self.services, 'Testing phase')

  def SignIn(self, user_id=111):
    self.mr.auth.user_pb = self.services.user.GetUser(self.cnxn, user_id)
    self.mr.auth.user_view = framework_views.UserView(self.mr.auth.user_pb)
    self.mr.auth.user_id = user_id
    self.mr.auth.effective_ids = {user_id}
    self.mr.perms = permissions.GetPermissions(
        self.mr.auth.user_pb, self.mr.auth.effective_ids, self.project)

  # FUTURE: GetSiteReadOnlyState()
  # FUTURE: SetSiteReadOnlyState()
  # FUTURE: GetSiteBannerMessage()
  # FUTURE: SetSiteBannerMessage()

  def testCreateProject_Normal(self):
    """We can create a project."""
    self.SignIn(user_id=self.admin_user.user_id)
    with self.work_env as we:
      project_id = we.CreateProject(
          'newproj', [111], [222], [333], 'summary', 'desc')
      actual = we.GetProject(project_id)

    self.assertEqual('summary', actual.summary)
    self.assertEqual('desc', actual.description)
    self.services.template.CreateDefaultProjectTemplates\
        .assert_called_once_with(self.mr.cnxn, project_id)

  def testCreateProject_AlreadyExists(self):
    """We can create a project."""
    self.SignIn(user_id=self.admin_user.user_id)
    # Project 'proj' is created in setUp().
    with self.assertRaises(exceptions.ProjectAlreadyExists):
      with self.work_env as we:
        we.CreateProject('proj', [111], [222], [333], 'summary', 'desc')

    self.assertFalse(
        self.services.template.CreateDefaultProjectTemplates.called)

  def testCreateProject_NotAllowed(self):
    """A user without permissions cannon create a project."""
    self.SignIn()
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.CreateProject('proj', [111], [222], [333], 'summary', 'desc')

    self.assertFalse(
        self.services.template.CreateDefaultProjectTemplates.called)

  def testCheckProjectName_OK(self):
    """We can check a project name."""
    self.SignIn(user_id=self.admin_user.user_id)
    with self.work_env as we:
      self.assertIsNone(we.CheckProjectName('foo'))

  def testCheckProjectName_InvalidProjectName(self):
    """We can check an invalid project name."""
    self.SignIn(user_id=self.admin_user.user_id)
    with self.work_env as we:
      self.assertIsNotNone(we.CheckProjectName('Foo'))

  def testCheckProjectName_AlreadyExists(self):
    """There is already a project with that name."""
    self.SignIn(user_id=self.admin_user.user_id)
    with self.work_env as we:
      self.assertIsNotNone(we.CheckProjectName('proj'))

  def testCheckProjectName_NotAllowed(self):
    """Users that can't create a project shouldn't get any information."""
    self.SignIn()
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.CheckProjectName('Foo')

  def testCheckComponentName_OK(self):
    self.SignIn()
    with self.work_env as we:
      self.assertIsNone(we.CheckComponentName(
          self.project.project_id, None, 'Component'))

  def testCheckComponentName_ParentComponentOK(self):
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Component', 'Docstring',
        False, [], [], 0, 111, [])
    self.SignIn()
    with self.work_env as we:
      self.assertIsNone(we.CheckComponentName(
          self.project.project_id, 'Component', 'SubComponent'))

  def testCheckComponentName_InvalidComponentName(self):
    self.SignIn()
    with self.work_env as we:
      self.assertIsNotNone(we.CheckComponentName(
          self.project.project_id, None, 'Component>Foo'))

  def testCheckComponentName_ComponentAlreadyExists(self):
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Component', 'Docstring',
        False, [], [], 0, 111, [])
    self.SignIn()
    with self.work_env as we:
      self.assertIsNotNone(we.CheckComponentName(
          self.project.project_id, None, 'Component'))

  def testCheckComponentName_NotAllowedToViewProject(self):
    self.project.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    self.SignIn(333)
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.CheckComponentName(self.project.project_id, None, 'Component')

  def testCheckComponentName_ParentComponentDoesntExist(self):
    self.SignIn()
    with self.assertRaises(exceptions.NoSuchComponentException):
      with self.work_env as we:
        we.CheckComponentName(
            self.project.project_id, 'Component', 'SubComponent')

  def testCheckFieldName_OK(self):
    self.SignIn()
    with self.work_env as we:
      self.assertIsNone(we.CheckFieldName(
          self.project.project_id, 'Field'))

  def testCheckFieldName_InvalidFieldName(self):
    self.SignIn()
    with self.work_env as we:
      self.assertIsNotNone(we.CheckFieldName(
          self.project.project_id, '**Field**'))

  def testCheckFieldName_FieldAlreadyExists(self):
    self.services.config.CreateFieldDef(
        self.cnxn, self.project.project_id, 'Field', 'STR_TYPE', None, None,
        None, None, None, None, None, None, None, None, None, None, None, None,
        None)
    self.SignIn()
    with self.work_env as we:
      self.assertIsNotNone(we.CheckFieldName(
          self.project.project_id, 'Field'))

  def testCheckFieldName_FieldIsPrefixOfAnother(self):
    self.services.config.CreateFieldDef(
        self.cnxn, self.project.project_id, 'Foo', 'STR_TYPE', None, None,
        None, None, None, None, None, None, None, None, None, None, None, None,
        None)
    self.services.config.CreateFieldDef(
        self.cnxn, self.project.project_id, 'Field-Foo', 'STR_TYPE', None, None,
        None, None, None, None, None, None, None, None, None, None, None, None,
        None)
    self.SignIn()
    with self.work_env as we:
      self.assertIsNotNone(we.CheckFieldName(
          self.project.project_id, 'Field'))

  def testCheckFieldName_AnotherFieldIsPrefix(self):
    self.services.config.CreateFieldDef(
        self.cnxn, self.project.project_id, 'Field', 'STR_TYPE', None, None,
        None, None, None, None, None, None, None, None, None, None, None, None,
        None)
    self.SignIn()
    with self.work_env as we:
      self.assertIsNotNone(we.CheckFieldName(
          self.project.project_id, 'Field-Foo'))

  def testCheckFieldName_ReservedPrefix(self):
    self.SignIn()
    with self.work_env as we:
      self.assertIsNotNone(we.CheckFieldName(
          self.project.project_id, 'Summary'))

  def testCheckFieldName_ReservedSuffix(self):
    self.SignIn()
    with self.work_env as we:
      self.assertIsNotNone(we.CheckFieldName(
          self.project.project_id, 'Chicken-ApproveR'))

  def testCheckFieldName_NotAllowedToViewProject(self):
    self.project.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    self.SignIn(user_id=333)
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.CheckFieldName(self.project.project_id, 'Field')

  def testListProjects(self):
    """We can get the project IDs of projects visible to the current user."""
    # Project 789 is created in setUp()
    self.services.project.TestAddProject(
        'proj2', project_id=2, access=project_pb2.ProjectAccess.MEMBERS_ONLY)
    self.services.project.TestAddProject('proj3', project_id=3)
    with self.work_env as we:
      actual = we.ListProjects()

    self.assertEqual([3, 789], actual)

  def testGetProject_Normal(self):
    """We can get an existing project by project_id."""
    with self.work_env as we:
      actual = we.GetProject(789)

    self.assertEqual(self.project, actual)

  def testGetProject_NoSuchProject(self):
    """We reject attempts to get a non-existent project."""
    with self.assertRaises(exceptions.NoSuchProjectException):
      with self.work_env as we:
        _actual = we.GetProject(999)

  def testGetProject_NotAllowed(self):
    """We reject attempts to get a project we don't have permission to."""
    self.project.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        _actual = we.GetProject(789)

  def testGetProjectByName_Normal(self):
    """We can get an existing project by project_name."""
    with self.work_env as we:
      actual = we.GetProjectByName('proj')

    self.assertEqual(self.project, actual)

  def testGetProjectByName_NoSuchProject(self):
    """We reject attempts to get a non-existent project."""
    with self.assertRaises(exceptions.NoSuchProjectException):
      with self.work_env as we:
        _actual = we.GetProjectByName('huh-what')

  def testGetProjectByName_NoPermission(self):
    """We reject attempts to get a project we don't have permissions to."""
    self.project.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        _actual = we.GetProjectByName('proj')

  def AddUserProjects(self):
    project_states = {
        'live': project_pb2.ProjectState.LIVE,
        'archived': project_pb2.ProjectState.ARCHIVED,
        'deletable': project_pb2.ProjectState.DELETABLE}

    projects = {}
    for name, state in project_states.items():
      projects['owner-'+name] = self.services.project.TestAddProject(
          'owner-' + name, state=state, owner_ids=[222])
      projects['committer-'+name] = self.services.project.TestAddProject(
          'committer-' + name, state=state, committer_ids=[222])
      projects['contributor-'+name] = self.services.project.TestAddProject(
          'contributor-' + name, state=state)
      projects['contributor-'+name].contributor_ids = [222]

    projects['members-only'] = self.services.project.TestAddProject(
        'members-only', owner_ids=[222])
    projects['members-only'].access = (
        project_pb2.ProjectAccess.MEMBERS_ONLY)

    return projects

  def testGetUserRolesInAllProjects_OtherUsers(self):
    """We can get the projects in which the user has a role."""
    projects = self.AddUserProjects()

    with self.work_env as we:
      owner, member, contrib = we.GetUserRolesInAllProjects({222})

    by_name = lambda project: project.project_name
    self.assertEqual(
        [projects['owner-live']],
        sorted(list(owner.values()), key=by_name))
    self.assertEqual(
        [projects['committer-live']],
        sorted(list(member.values()), key=by_name))
    self.assertEqual(
        [projects['contributor-live']],
        sorted(list(contrib.values()), key=by_name))

  def testGetUserRolesInAllProjects_OwnUser(self):
    """We can get the projects in which the user has a role."""
    projects = self.AddUserProjects()

    self.SignIn(user_id=222)
    with self.work_env as we:
      owner, member, contrib = we.GetUserRolesInAllProjects({222})

    by_name = lambda project: project.project_name
    self.assertEqual(
        [projects['members-only'], projects['owner-archived'],
         projects['owner-live']],
        sorted(list(owner.values()), key=by_name))
    self.assertEqual(
        [projects['committer-archived'], projects['committer-live']],
        sorted(list(member.values()), key=by_name))
    self.assertEqual(
        [projects['contributor-archived'], projects['contributor-live']],
        sorted(list(contrib.values()), key=by_name))

  def testGetUserRolesInAllProjects_Admin(self):
    """We can get the projects in which the user has a role."""
    projects = self.AddUserProjects()

    self.SignIn(user_id=444)
    with self.work_env as we:
      owner, member, contrib = we.GetUserRolesInAllProjects({222})

    by_name = lambda project: project.project_name
    self.assertEqual(
        [projects['members-only'], projects['owner-archived'],
         projects['owner-deletable'], projects['owner-live']],
        sorted(list(owner.values()), key=by_name))
    self.assertEqual(
        [projects['committer-archived'], projects['committer-deletable'],
         projects['committer-live']],
        sorted(list(member.values()), key=by_name))
    self.assertEqual(
        [projects['contributor-archived'], projects['contributor-deletable'],
         projects['contributor-live']],
        sorted(list(contrib.values()), key=by_name))

  def testGetUserProjects_OnlyLiveOfOtherUsers(self):
    """Regular users should only see live projects of other users."""
    projects = self.AddUserProjects()

    self.SignIn()
    with self.work_env as we:
      owner, archived, member, contrib = we.GetUserProjects({222})

    self.assertEqual([projects['owner-live']], owner)
    self.assertEqual([], archived)
    self.assertEqual([projects['committer-live']], member)
    self.assertEqual([projects['contributor-live']], contrib)

  def testGetUserProjects_AdminSeesAll(self):
    """Admins should see all projects from other users."""
    projects = self.AddUserProjects()

    self.SignIn(user_id=444)
    with self.work_env as we:
      owner, archived, member, contrib = we.GetUserProjects({222})

    self.assertEqual([projects['members-only'], projects['owner-live']], owner)
    self.assertEqual([projects['owner-archived']], archived)
    self.assertEqual([projects['committer-live']], member)
    self.assertEqual([projects['contributor-live']], contrib)

  def testGetUserProjects_UserSeesOwnProjects(self):
    """Users should see all own projects."""
    projects = self.AddUserProjects()

    self.SignIn(user_id=222)
    with self.work_env as we:
      owner, archived, member, contrib = we.GetUserProjects({222})

    self.assertEqual([projects['members-only'], projects['owner-live']], owner)
    self.assertEqual([projects['owner-archived']], archived)
    self.assertEqual([projects['committer-live']], member)
    self.assertEqual([projects['contributor-live']], contrib)

  def testUpdateProject_Normal(self):
    """We can update an existing project."""
    self.SignIn(user_id=self.admin_user.user_id)
    with self.work_env as we:
      we.UpdateProject(789, read_only_reason='test reason')
      project = we.GetProject(789)

    self.assertEqual('test reason', project.read_only_reason)

  def testUpdateProject_NoSuchProject(self):
    """Updating a nonexistent project raises an exception."""
    self.SignIn(user_id=self.admin_user.user_id)
    with self.assertRaises(exceptions.NoSuchProjectException):
      with self.work_env as we:
        we.UpdateProject(999, summary='new summary')

  def testDeleteProject_Normal(self):
    """We can mark an existing project as deletable."""
    self.SignIn(user_id=self.admin_user.user_id)
    with self.work_env as we:
      we.DeleteProject(789)

    self.assertEqual(project_pb2.ProjectState.DELETABLE, self.project.state)

  def testDeleteProject_NoSuchProject(self):
    """Changing a nonexistent project raises an exception."""
    self.SignIn(user_id=self.admin_user.user_id)
    with self.assertRaises(exceptions.NoSuchProjectException):
      with self.work_env as we:
        we.DeleteProject(999)

  def testStarProject_Normal(self):
    """We can star and unstar a project."""
    self.SignIn()
    with self.work_env as we:
      self.assertFalse(we.IsProjectStarred(789))
      we.StarProject(789, True)
      self.assertTrue(we.IsProjectStarred(789))
      we.StarProject(789, False)
      self.assertFalse(we.IsProjectStarred(789))

  def testStarProject_NoSuchProject(self):
    """We can't star a nonexistent project."""
    self.SignIn()
    with self.assertRaises(exceptions.NoSuchProjectException):
      with self.work_env as we:
        we.StarProject(999, True)

  def testStarProject_Anon(self):
    """Anon user can't star a project."""
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.StarProject(789, True)

  def testIsProjectStarred_Normal(self):
    """We can check if a project is starred."""
    # Tested by method testStarProject_Normal().
    pass

  def testIsProjectStarred_NoProjectSpecified(self):
    """A project ID must be specified."""
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException):
        self.assertFalse(we.IsProjectStarred(None))

  def testIsProjectStarred_NoSuchProject(self):
    """We can't check for stars on a nonexistent project."""
    self.SignIn()
    with self.assertRaises(exceptions.NoSuchProjectException):
      with self.work_env as we:
        we.IsProjectStarred(999)

  def testGetProjectStarCount_Normal(self):
    """We can count the stars of a project."""
    self.SignIn()
    with self.work_env as we:
      self.assertEqual(0, we.GetProjectStarCount(789))
      we.StarProject(789, True)
      self.assertEqual(1, we.GetProjectStarCount(789))

    self.SignIn(user_id=self.admin_user.user_id)
    with self.work_env as we:
      we.StarProject(789, True)
      self.assertEqual(2, we.GetProjectStarCount(789))
      we.StarProject(789, False)
      self.assertEqual(1, we.GetProjectStarCount(789))

  def testGetProjectStarCount_NoSuchProject(self):
    """We can't count stars of a nonexistent project."""
    self.SignIn()
    with self.assertRaises(exceptions.NoSuchProjectException):
      with self.work_env as we:
        we.GetProjectStarCount(999)

  def testGetProjectStarCount_NoProjectSpecified(self):
    """A project ID must be specified."""
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException):
        self.assertFalse(we.GetProjectStarCount(None))

  def testListStarredProjects_ViewingSelf(self):
    """A user can view their own starred projects, if they still have access."""
    project1 = self.services.project.TestAddProject('proj1', project_id=1)
    project2 = self.services.project.TestAddProject('proj2', project_id=2)
    with self.work_env as we:
      self.SignIn()
      we.StarProject(project1.project_id, True)
      we.StarProject(project2.project_id, True)
      self.assertItemsEqual(
        [project1, project2], we.ListStarredProjects())
      project2.access = project_pb2.ProjectAccess.MEMBERS_ONLY
      self.assertItemsEqual(
        [project1], we.ListStarredProjects())

  def testListStarredProjects_ViewingOther(self):
    """A user can view their own starred projects, if they still have access."""
    project1 = self.services.project.TestAddProject('proj1', project_id=1)
    project2 = self.services.project.TestAddProject('proj2', project_id=2)
    with self.work_env as we:
      self.SignIn(user_id=222)
      we.StarProject(project1.project_id, True)
      we.StarProject(project2.project_id, True)
      self.SignIn(user_id=111)
      self.assertEqual([], we.ListStarredProjects())
      self.assertItemsEqual(
        [project1, project2], we.ListStarredProjects(viewed_user_id=222))
      project2.access = project_pb2.ProjectAccess.MEMBERS_ONLY
      self.assertItemsEqual(
        [project1], we.ListStarredProjects(viewed_user_id=222))

  def testGetProjectConfig_Normal(self):
    """We can get an existing config by project_id."""
    config = fake.MakeTestConfig(789, ['LabelOne'], ['New'])
    self.services.config.StoreConfig('cnxn', config)
    with self.work_env as we:
      actual = we.GetProjectConfig(789)

    self.assertEqual(config, actual)

  def testGetProjectConfig_NoSuchProject(self):
    """We reject attempts to get a non-existent config."""
    self.services.config.strict = True
    with self.assertRaises(exceptions.NoSuchProjectException):
      with self.work_env as we:
        _actual = we.GetProjectConfig(789)

  def testListProjectTemplates_IsMember(self):
    private_tmpl = tracker_pb2.TemplateDef(name='Chicken', members_only=True)
    public_tmpl = tracker_pb2.TemplateDef(name='Kale', members_only=False)
    self.services.template.GetProjectTemplates.return_value = [
        private_tmpl, public_tmpl]

    self.SignIn()  # user 111 is a member of self.project

    with self.work_env as we:
      actual = we.ListProjectTemplates(self.project)

    self.assertEqual(actual, [private_tmpl, public_tmpl])
    self.services.template.GetProjectTemplates.assert_called_once_with(
        self.mr.cnxn, self.project.project_id)

  def testListProjectTemplates_IsNotMember(self):
    private_tmpl = tracker_pb2.TemplateDef(name='Chicken', members_only=True)
    public_tmpl = tracker_pb2.TemplateDef(name='Kale', members_only=False)
    self.services.template.GetProjectTemplates.return_value = [
        private_tmpl, public_tmpl]

    with self.work_env as we:
      actual = we.ListProjectTemplates(self.project)

    self.assertEqual(actual, [public_tmpl])
    self.services.template.GetProjectTemplates.assert_called_once_with(
        self.mr.cnxn, self.project.project_id)

  # FUTURE: labels, statuses, fields, components, rules, templates, and views.
  # FUTURE: project saved queries.
  # FUTURE: GetProjectPermissionsForUser()

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueBlockingNotification')
  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testCreateIssue_Normal(self, fake_pasicn, fake_pasibn):
    """We can create an issue."""
    self.SignIn(user_id=111)
    approval_values = [tracker_pb2.ApprovalValue(approval_id=23, phase_id=3)]
    phases = [tracker_pb2.Phase(name='Canary', phase_id=3)]
    with self.work_env as we:
      actual_issue, comment = we.CreateIssue(
          789, 'sum', 'New', 222, [333], ['Hot'], [], [], 'desc',
          phases=phases, approval_values=approval_values)
    self.assertEqual(789, actual_issue.project_id)
    self.assertEqual('sum', actual_issue.summary)
    self.assertEqual('New', actual_issue.status)
    self.assertEqual(111, actual_issue.reporter_id)
    self.assertEqual(222, actual_issue.owner_id)
    self.assertEqual([333], actual_issue.cc_ids)
    self.assertEqual([], actual_issue.field_values)
    self.assertEqual([], actual_issue.component_ids)
    self.assertEqual(approval_values, actual_issue.approval_values)
    self.assertEqual(phases, actual_issue.phases)
    self.assertEqual('desc', comment.content)
    loaded_comments = self.services.issue.GetCommentsForIssue(
        self.cnxn, actual_issue.issue_id)
    self.assertEqual('desc', loaded_comments[0].content)

    # Verify that an indexing task was enqueued for this issue:
    self.assertTrue(self.services.issue.enqueue_issues_called)
    self.assertEqual(1, len(self.services.issue.enqueued_issues))
    self.assertEqual(actual_issue.issue_id,
        self.services.issue.enqueued_issues[0])

    # Verify that tasks were queued to send email notifications.
    hostport = 'testing-app.appspot.com'
    fake_pasicn.assert_called_once_with(
        actual_issue.issue_id, hostport, 111, comment_id=comment.id)
    fake_pasibn.assert_called_once_with(
        actual_issue.issue_id, hostport, [], 111)

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueBlockingNotification')
  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testCreateIssue_DontSendEmail(self, fake_pasicn, fake_pasibn):
    """We can create an issue, without queueing notification tasks."""
    self.SignIn(user_id=111)
    with self.work_env as we:
      actual_issue, comment = we.CreateIssue(
          789, 'sum', 'New', 222, [333], ['Hot'], [], [], 'desc',
          send_email=False)
    self.assertEqual(789, actual_issue.project_id)
    self.assertEqual('sum', actual_issue.summary)
    self.assertEqual('New', actual_issue.status)
    self.assertEqual('desc', comment.content)

    # Verify that tasks were not queued to send email notifications.
    self.assertEqual([], fake_pasicn.mock_calls)
    self.assertEqual([], fake_pasibn.mock_calls)

  @mock.patch('services.tracker_fulltext.IndexIssues')
  @mock.patch('services.tracker_fulltext.UnindexIssues')
  def testMoveIssue_Normal(self, mock_unindex, mock_index):
    """We can move issues."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    self.project.owner_ids = [111]
    target_project = self.services.project.TestAddProject(
      'dest', project_id=988, committer_ids=[111])

    self.SignIn(user_id=111)
    with self.work_env as we:
      moved_issue = we.MoveIssue(issue, target_project)

    self.assertEqual(moved_issue.project_name, 'dest')
    self.assertEqual(moved_issue.local_id, 1)

    moved_issue = self.services.issue.GetIssueByLocalID(
        'cnxn', target_project.project_id, 1)
    self.assertEqual(target_project.project_id, moved_issue.project_id)
    self.assertEqual(issue.summary, moved_issue.summary)
    self.assertEqual(moved_issue.reporter_id, 111)

    mock_unindex.assert_called_once_with([issue.issue_id])
    mock_index.assert_called_once_with(
       self.mr.cnxn, [issue], self.services.user, self.services.issue,
       self.services.config)

  @mock.patch('services.tracker_fulltext.IndexIssues')
  @mock.patch('services.tracker_fulltext.UnindexIssues')
  def testMoveIssue_MoveBackAgain(self, _mock_unindex, _mock_index):
    """We can move issues backt and get the old id."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    issue.project_name = 'proj'
    self.services.issue.TestAddIssue(issue)
    self.project.owner_ids = [111]
    target_project = self.services.project.TestAddProject(
      'dest', project_id=988, owner_ids=[111])

    self.SignIn(user_id=111)
    with self.work_env as we:
      moved_issue = we.MoveIssue(issue, target_project)
      moved_issue = we.MoveIssue(moved_issue, self.project)

    self.assertEqual(moved_issue.project_name, 'proj')
    self.assertEqual(moved_issue.local_id, 1)

    moved_issue = self.services.issue.GetIssueByLocalID(
        'cnxn', self.project.project_id, 1)
    self.assertEqual(self.project.project_id, moved_issue.project_id)

    comments = self.services.issue.GetCommentsForIssue('cnxn', issue.issue_id)
    self.assertEqual(
        comments[1].content, 'Moved issue proj:1 to now be issue dest:1.')
    self.assertEqual(
        comments[2].content, 'Moved issue dest:1 back to issue proj:1 again.')

  def testMoveIssue_Anon(self):
    """Anon can't move issues."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    target_project = self.services.project.TestAddProject(
      'dest', project_id=988)

    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.MoveIssue(issue, target_project)

  def testMoveIssue_CantDeleteIssue(self):
    """We can't move issues if we don't have DeleteIssue perm on the issue."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    target_project = self.services.project.TestAddProject(
      'dest', project_id=988, committer_ids=[111])

    self.SignIn(user_id=111)
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.MoveIssue(issue, target_project)

  def testMoveIssue_CantEditIssueOnTargetProject(self):
    """We can't move issues if we don't have EditIssue perm on target."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    self.project.owner_ids = [111]
    target_project = self.services.project.TestAddProject(
      'dest', project_id=989)

    self.SignIn(user_id=111)
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.MoveIssue(issue, target_project)

  def testMoveIssue_CantRestrictions(self):
    """We can't move issues if they have restriction labels."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    issue.labels = ['Restrict-Foo-Bar']
    self.services.issue.TestAddIssue(issue)
    self.project.owner_ids = [111]
    target_project = self.services.project.TestAddProject(
      'dest', project_id=989, committer_ids=[111])

    self.SignIn(user_id=111)
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.MoveIssue(issue, target_project)

  @mock.patch('services.tracker_fulltext.IndexIssues')
  def testCopyIssue_Normal(self, mock_index):
    """We can copy issues."""
    issue = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, issue_id=78901, project_name='proj')
    self.services.issue.TestAddIssue(issue)
    self.project.owner_ids = [111]
    target_project = self.services.project.TestAddProject(
      'dest', project_id=988, committer_ids=[111])

    self.SignIn(user_id=111)
    with self.work_env as we:
      copied_issue = we.CopyIssue(issue, target_project)

    self.assertEqual(copied_issue.project_name, 'dest')
    self.assertEqual(copied_issue.local_id, 1)

    # Original issue should still exist.
    self.services.issue.GetIssueByLocalID('cnxn', 789, 1)

    copied_issue = self.services.issue.GetIssueByLocalID(
        'cnxn', target_project.project_id, 1)
    self.assertEqual(target_project.project_id, copied_issue.project_id)
    self.assertEqual(issue.summary, copied_issue.summary)
    self.assertEqual(copied_issue.reporter_id, 111)

    mock_index.assert_called_once_with(
       self.mr.cnxn, [copied_issue], self.services.user, self.services.issue,
       self.services.config)

    comment = self.services.issue.GetCommentsForIssue(
        'cnxn', copied_issue.issue_id)[-1]
    self.assertEqual(1, len(comment.amendments))
    amendment = comment.amendments[0]
    self.assertEqual(
        tracker_pb2.Amendment(
            field=tracker_pb2.FieldID.PROJECT,
            newvalue='dest',
            added_user_ids=[],
            removed_user_ids=[]),
        amendment)

  @mock.patch('services.tracker_fulltext.IndexIssues')
  def testCopyIssue_SameProject(self, mock_index):
    """We can copy issues."""
    issue = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, issue_id=78901, project_name='proj')
    self.services.issue.TestAddIssue(issue)
    self.project.owner_ids = [111]
    target_project = self.project

    self.SignIn(user_id=111)
    with self.work_env as we:
      copied_issue = we.CopyIssue(issue, target_project)

    self.assertEqual(copied_issue.project_name, 'proj')
    self.assertEqual(copied_issue.local_id, 2)

    # Original issue should still exist.
    self.services.issue.GetIssueByLocalID('cnxn', 789, 1)

    copied_issue = self.services.issue.GetIssueByLocalID(
        'cnxn', target_project.project_id, 2)
    self.assertEqual(target_project.project_id, copied_issue.project_id)
    self.assertEqual(issue.summary, copied_issue.summary)
    self.assertEqual(copied_issue.reporter_id, 111)

    mock_index.assert_called_once_with(
       self.mr.cnxn, [copied_issue], self.services.user, self.services.issue,
       self.services.config)
    comment = self.services.issue.GetCommentsForIssue(
        'cnxn', copied_issue.issue_id)[-1]
    self.assertEqual(0, len(comment.amendments))

  def testCopyIssue_Anon(self):
    """Anon can't copy issues."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    target_project = self.services.project.TestAddProject(
      'dest', project_id=988)

    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.CopyIssue(issue, target_project)

  def testCopyIssue_CantDeleteIssue(self):
    """We can't copy issues if we don't have DeleteIssue perm on the issue."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    target_project = self.services.project.TestAddProject(
      'dest', project_id=988, committer_ids=[111])

    self.SignIn(user_id=111)
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.CopyIssue(issue, target_project)

  def testCopyIssue_CantEditIssueOnTargetProject(self):
    """We can't copy issues if we don't have EditIssue perm on target."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    self.project.owner_ids = [111]
    target_project = self.services.project.TestAddProject(
      'dest', project_id=989)

    self.SignIn(user_id=111)
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.CopyIssue(issue, target_project)

  def testCopyIssue_CantRestrictions(self):
    """We can't copy issues if they have restriction labels."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    issue.labels = ['Restrict-Foo-Bar']
    self.services.issue.TestAddIssue(issue)
    self.project.owner_ids = [111]
    target_project = self.services.project.TestAddProject(
      'dest', project_id=989, committer_ids=[111])

    self.SignIn(user_id=111)
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.CopyIssue(issue, target_project)

  def testListIssues_Normal(self):
    """We can do a query that generates some results."""
    pass  # TODO(jrobbins): add unit test

  def testListIssues_Error(self):
    """Errors are safely reported."""
    pass  # TODO(jrobbins): add unit test

  def testFindIssuePositionInSearch_Normal(self):
    """We can find an issue position for the flipper."""
    pass  # TODO(jrobbins): add unit test

  def testFindIssuePositionInSearch_Error(self):
    """Errors are safely reported."""
    pass  # TODO(jrobbins): add unit test

  def testGetIssuesDict_Normal(self):
    """We can get an existing issue by issue_id."""
    issue_1 = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue_1)
    issue_2 = fake.MakeTestIssue(789, 2, 'sum', 'New', 111, issue_id=78902)
    issue_2.labels = ['Restrict-View-CoreTeam']
    self.services.issue.TestAddIssue(issue_2)
    issue_3 = fake.MakeTestIssue(789, 3, 'sum', 'New', 111, issue_id=78903)
    self.services.issue.TestAddIssue(issue_3)

    with self.work_env as we:
      actual = we.GetIssuesDict([78901, 78902, 78903])

    # We don't have permission to view issue 2, so it should be filtered out.
    self.assertEqual({78901: issue_1, 78903: issue_3}, actual)

  def testGetIssuesDict_NoSuchIssue(self):
    """We reject attempts to get a non-existent issue."""
    with self.assertRaises(exceptions.NoSuchIssueException):
      with self.work_env as we:
        _actual = we.GetIssuesDict([78901])


  def testGetIssue_Normal(self):
    """We can get an existing issue by issue_id."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    with self.work_env as we:
      actual = we.GetIssue(78901)

    self.assertEqual(issue, actual)

  def testGetIssue_NoPermission(self):
    """We reject attempts to get an issue we don't have permission for."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    issue.labels = ['Restrict-View-CoreTeam']
    self.services.issue.TestAddIssue(issue)

    # We should get a permission exception
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        _actual = we.GetIssue(78901)

    # ...unless we have permission to see the issue
    self.SignIn(user_id=self.admin_user.user_id)
    with self.work_env as we:
      actual = we.GetIssue(78901)
    self.assertEqual(issue, actual)

  def testGetIssue_NoneIssue(self):
    """We reject attempts to get a none issue."""
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        _actual = we.GetIssue(None)

  def testGetIssue_NoSuchIssue(self):
    """We reject attempts to get a non-existent issue."""
    with self.assertRaises(exceptions.NoSuchIssueException):
      with self.work_env as we:
        _actual = we.GetIssue(78901)

  def testListReferencedIssues(self):
    """We return only existing or visible issues even w/out project names."""
    ref_tuples = [
        (None, 1), ('other-proj', 1), ('proj', 99),
        ('ghost-proj', 1), ('proj', 42), ('other-proj', 1)]
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    private = fake.MakeTestIssue(789, 42, 'sum', 'New', 422, issue_id=78942)
    private.labels.append('Restrict-View-CoreTeam')
    self.services.issue.TestAddIssue(private)
    self.services.project.TestAddProject(
        'other-proj', project_id=788)
    other_issue = fake.MakeTestIssue(
        788, 1, 'sum', 'Fixed', 111, issue_id=78801)
    self.services.issue.TestAddIssue(other_issue)

    with self.work_env as we:
      actual_open, actual_closed = we.ListReferencedIssues(ref_tuples, 'proj')

    self.assertEqual([issue], actual_open)
    self.assertEqual([other_issue], actual_closed)

  def testListReferencedIssues_PreservesOrder(self):
    ref_tuples = [('proj', i) for i in range(1, 10)]
    # Duplicate some ref_tuples. The result should have no duplicated issues,
    # with only the first occurrence being preserved.
    ref_tuples += [('proj', 1), ('proj', 5)]
    expected_open = [
        fake.MakeTestIssue(789, i, 'sum', 'New', 111) for i in range(1, 5)]
    expected_closed = [
        fake.MakeTestIssue(789, i, 'sum', 'Fixed', 111) for i in range(5, 10)]
    for issue in expected_open + expected_closed:
      self.services.issue.TestAddIssue(issue)

    with self.work_env as we:
      actual_open, actual_closed = we.ListReferencedIssues(ref_tuples, 'proj')

    self.assertEqual(expected_open, actual_open)
    self.assertEqual(expected_closed, actual_closed)

  def testListApplicableFieldDefs(self):
    issue_1 = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, issue_id=78901,
        labels=['type-defect', 'other-label'])
    issue_2 = fake.MakeTestIssue(
        789, 2, 'sum', 'New', 111, issue_id=78902,
        labels=['type-feedback', 'other-label1'])
    issue_3 = fake.MakeTestIssue(
        789, 3, 'sum', 'New', 111, issue_id=78903,
        labels=['type-defect'],
        approval_values=[tracker_pb2.ApprovalValue(approval_id=3),
                         tracker_pb2.ApprovalValue(approval_id=5)])
    issue_4 = fake.MakeTestIssue(
        789, 4, 'sum', 'New', 111, issue_id=78904)  # test no labels at all
    issue_5 = fake.MakeTestIssue(
        789, 5, 'sum', 'New', 111, issue_id=78905,
        labels=['type'],  # test labels ignored
        approval_values=[tracker_pb2.ApprovalValue(approval_id=5)])
    self.services.issue.TestAddIssue(issue_1)
    self.services.issue.TestAddIssue(issue_2)
    self.services.issue.TestAddIssue(issue_3)
    self.services.issue.TestAddIssue(issue_4)
    self.services.issue.TestAddIssue(issue_5)
    fd_1 = tracker_pb2.FieldDef(field_name='FirstField', field_id=1,
                                field_type=tracker_pb2.FieldTypes.STR_TYPE,
                                applicable_type='feedback')  # applicable
    fd_2 = tracker_pb2.FieldDef(field_name='SecField', field_id=2,
                                field_type=tracker_pb2.FieldTypes.INT_TYPE,
                                applicable_type='no')  # not applicable
    fd_3 = tracker_pb2.FieldDef(field_name='LegalApproval', field_id=3,
                                field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE,
                                applicable_type='')  # applicable
    fd_4 = tracker_pb2.FieldDef(field_name='UserField', field_id=4,
                                field_type=tracker_pb2.FieldTypes.USER_TYPE,
                                applicable_type='')  # applicable
    fd_5 = tracker_pb2.FieldDef(field_name='DogApproval', field_id=5,
                                field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE,
                                applicable_type='')  # applicable
    fd_6 = tracker_pb2.FieldDef(field_name='SixthField', field_id=6,
                                field_type=tracker_pb2.FieldTypes.INT_TYPE,
                                applicable_type='Defect')  # applicable
    fd_7 = tracker_pb2.FieldDef(field_name='CatApproval', field_id=7,
                                field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE,
                                applicable_type='')  # not applicable
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.field_defs = [fd_1, fd_2, fd_3, fd_4, fd_5, fd_6, fd_7]
    issue_ids = [issue_1.issue_id, issue_2.issue_id, issue_3.issue_id,
                 issue_4.issue_id, issue_5.issue_id]
    with self.work_env as we:
      actual_fds = we.ListApplicableFieldDefs(issue_ids, config)
    self.assertEqual(actual_fds, [fd_1, fd_3, fd_4, fd_5, fd_6])

  def testGetIssueByLocalID_Normal(self):
    """We can get an existing issue by project_id and local_id."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    with self.work_env as we:
      actual = we.GetIssueByLocalID(789, 1)

    self.assertEqual(issue, actual)

  def testGetIssueByLocalID_ProjectNotSpecified(self):
    """We reject calls with missing information."""
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        _actual = we.GetIssueByLocalID(None, 1)

  def testGetIssueByLocalID_IssueNotSpecified(self):
    """We reject calls with missing information."""
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        _actual = we.GetIssueByLocalID(789, None)

  def testGetIssueByLocalID_NoSuchIssue(self):
    """We reject attempts to get a non-existent issue."""
    with self.assertRaises(exceptions.NoSuchIssueException):
      with self.work_env as we:
        _actual = we.GetIssueByLocalID(789, 1)

  def testGetRelatedIssueRefs_None(self):
    """We handle issues that have no related issues."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111)
    self.services.issue.TestAddIssue(issue)

    with self.work_env as we:
      actual = we.GetRelatedIssueRefs([issue])

    self.assertEqual({}, actual)

  def testGetRelatedIssueRefs_Some(self):
    """We can get refs for related issues of a given issue."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111)
    sooner = fake.MakeTestIssue(789, 2, 'sum', 'New', 111, project_name='proj')
    later = fake.MakeTestIssue(789, 3, 'sum', 'New', 111, project_name='proj')
    better = fake.MakeTestIssue(789, 4, 'sum', 'New', 111, project_name='proj')
    issue.blocked_on_iids.append(sooner.issue_id)
    issue.blocking_iids.append(later.issue_id)
    issue.merged_into = better.issue_id
    self.services.issue.TestAddIssue(issue)
    self.services.issue.TestAddIssue(sooner)
    self.services.issue.TestAddIssue(later)
    self.services.issue.TestAddIssue(better)

    with self.work_env as we:
      actual = we.GetRelatedIssueRefs([issue])

    self.assertEqual(
        {sooner.issue_id: ('proj', 2),
         later.issue_id: ('proj', 3),
         better.issue_id: ('proj', 4)},
        actual)

  def testGetRelatedIssueRefs_MultipleIssues(self):
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111)
    blocking = fake.MakeTestIssue(
        789, 2, 'sum', 'New', 111, project_name='proj')
    issue2 = fake.MakeTestIssue(789, 3, 'sum', 'New', 111, project_name='proj')
    blocked_on = fake.MakeTestIssue(
        789, 4, 'sum', 'New', 111, project_name='proj')
    issue3 = fake.MakeTestIssue(789, 5, 'sum', 'New', 111, project_name='proj')
    merged_into = fake.MakeTestIssue(
        789, 6, 'sum', 'New', 111, project_name='proj')

    issue.blocked_on_iids.append(blocked_on.issue_id)
    issue2.blocking_iids.append(blocking.issue_id)
    issue3.merged_into = merged_into.issue_id

    self.services.issue.TestAddIssue(issue)
    self.services.issue.TestAddIssue(issue2)
    self.services.issue.TestAddIssue(issue3)
    self.services.issue.TestAddIssue(blocked_on)
    self.services.issue.TestAddIssue(blocking)
    self.services.issue.TestAddIssue(merged_into)

    with self.work_env as we:
      actual = we.GetRelatedIssueRefs([issue, issue2, issue3])

    self.assertEqual(
        {blocking.issue_id: ('proj', 2),
         blocked_on.issue_id: ('proj', 4),
         merged_into.issue_id: ('proj', 6)},
        actual)

  def testGetIssueRefs(self):
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj1')
    issue2 = fake.MakeTestIssue(789, 3, 'sum', 'New', 111, project_name='proj')
    issue3 = fake.MakeTestIssue(789, 5, 'sum', 'New', 111, project_name='proj')

    self.services.issue.TestAddIssue(issue)
    self.services.issue.TestAddIssue(issue2)
    self.services.issue.TestAddIssue(issue3)

    with self.work_env as we:
      actual = we.GetIssueRefs(
          [issue.issue_id, issue2.issue_id, issue3.issue_id])

    self.assertEqual(
        {issue.issue_id: ('proj1', 1),
         issue2.issue_id: ('proj', 3),
         issue3.issue_id: ('proj', 5)},
        actual)

  @mock.patch('businesslogic.work_env.WorkEnv.UpdateIssueApproval')
  def testBulkUpdateIssueApproval(self, mockUpdateIssueApproval):
    updated_issues = [78901, 78902]
    def side_effect(issue_id, *_args, **_kwargs):
      if issue_id in [78903]:
        raise permissions.PermissionException
      if issue_id in [78904, 78905]:
        raise exceptions.NoSuchIssueApprovalException
    mockUpdateIssueApproval.side_effect = side_effect

    self.SignIn()

    approval_delta = tracker_pb2.ApprovalDelta()
    issue_ids = self.work_env.BulkUpdateIssueApprovals(
        [78901, 78902, 78903, 78904, 78905], 24, self.project, approval_delta,
        'comment', send_email=True)
    self.assertEqual(issue_ids, updated_issues)
    updateIssueApprovalCalls = [
        mock.call(
            78901, 24, approval_delta, 'comment', False, send_email=False),
        mock.call(
            78902, 24, approval_delta, 'comment', False, send_email=False),
        mock.call(
            78903, 24, approval_delta, 'comment', False, send_email=False),
        mock.call(
            78904, 24, approval_delta, 'comment', False, send_email=False),
        mock.call(
            78905, 24, approval_delta, 'comment', False, send_email=False),
    ]
    mockUpdateIssueApproval.assert_has_calls(updateIssueApprovalCalls)

  def testBulkUpdateIssueApproval_AnonUser(self):
    approval_delta = tracker_pb2.ApprovalDelta()
    with self.assertRaises(permissions.PermissionException):
      self.work_env.BulkUpdateIssueApprovals(
          [], 24, self.project, approval_delta,
          'comment', send_email=True)

  def testBulkUpdateIssueApproval_UserLacksViewPerms(self):
    approval_delta = tracker_pb2.ApprovalDelta()
    self.SignIn(222)
    self.project.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    with self.assertRaises(permissions.PermissionException):
      self.work_env.BulkUpdateIssueApprovals(
          [], 24, self.project, approval_delta,
          'comment', send_email=True)

  @mock.patch(
      'features.send_notifications.PrepareAndSendApprovalChangeNotification')
  def testUpdateIssueApproval(self, _mockPrepareAndSend):
    """We can update an issue's approval_value."""

    self.services.issue.DeltaUpdateIssueApproval = mock.Mock()

    self.SignIn()

    config = fake.MakeTestConfig(789, [], [])
    self.services.config.StoreConfig('cnxn', config)

    av_24 = tracker_pb2.ApprovalValue(
        approval_id=24, approver_ids=[111],
        status=tracker_pb2.ApprovalStatus.NOT_SET, set_on=1234, setter_id=999)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111,
                               issue_id=78901, approval_values=[av_24])
    self.services.issue.TestAddIssue(issue)

    delta = tracker_pb2.ApprovalDelta(
        status=tracker_pb2.ApprovalStatus.REVIEW_REQUESTED, set_on=2345,
        approver_ids_add=[222])

    self.work_env.UpdateIssueApproval(78901, 24, delta, 'please review', False)

    self.services.issue.DeltaUpdateIssueApproval.assert_called_once_with(
        self.mr.cnxn, 111, config, issue, av_24, delta,
        comment_content='please review', is_description=False, attachments=None,
        kept_attachments=None)

  @mock.patch(
      'features.send_notifications.PrepareAndSendApprovalChangeNotification')
  def testUpdateIssueApproval_IsDescription(self, _mockPrepareAndSend):
    """We can update an issue's approval survey."""

    self.services.issue.DeltaUpdateIssueApproval = mock.Mock()

    self.SignIn()

    config = fake.MakeTestConfig(789, [], [])
    self.services.config.StoreConfig('cnxn', config)

    av_24 = tracker_pb2.ApprovalValue(approval_id=24)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111,
                               issue_id=78901, approval_values=[av_24])
    self.services.issue.TestAddIssue(issue)

    delta = tracker_pb2.ApprovalDelta()
    self.work_env.UpdateIssueApproval(78901, 24, delta, 'better response', True)

    self.services.issue.DeltaUpdateIssueApproval.assert_called_once_with(
        self.mr.cnxn, 111, config, issue, av_24, delta,
        comment_content='better response', is_description=True,
        attachments=None, kept_attachments=None)

  @mock.patch(
      'features.send_notifications.PrepareAndSendApprovalChangeNotification')
  def testUpdateIssueApproval_Attachments(self, _mockPrepareAndSend):
    """We can attach files as we many an approval change."""
    self.services.issue.DeltaUpdateIssueApproval = mock.Mock()

    self.SignIn()

    config = fake.MakeTestConfig(789, [], [])
    self.services.config.StoreConfig('cnxn', config)

    av_24 = tracker_pb2.ApprovalValue(
        approval_id=24, approver_ids=[111],
        status=tracker_pb2.ApprovalStatus.NOT_SET, set_on=1234, setter_id=999)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111,
                               issue_id=78901, approval_values=[av_24])
    self.services.issue.TestAddIssue(issue)

    delta = tracker_pb2.ApprovalDelta(
        status=tracker_pb2.ApprovalStatus.REVIEW_REQUESTED, set_on=2345,
        approver_ids_add=[222])
    attachments = []
    self.work_env.UpdateIssueApproval(78901, 24, delta, 'please review', False,
                                      attachments=attachments)

    self.services.issue.DeltaUpdateIssueApproval.assert_called_once_with(
        self.mr.cnxn, 111, config, issue, av_24, delta,
        comment_content='please review', is_description=False,
        attachments=attachments, kept_attachments=None)

  @mock.patch(
      'features.send_notifications.PrepareAndSendApprovalChangeNotification')
  @mock.patch(
      'tracker.tracker_helpers.FilterKeptAttachments')
  def testUpdateIssueApproval_KeptAttachments(
      self, mockFilterKeptAttachments, _mockPrepareAndSend):
    """We can keep attachments from previous descriptions."""
    self.services.issue.DeltaUpdateIssueApproval = mock.Mock()
    mockFilterKeptAttachments.return_value = [1, 2]

    self.SignIn()

    config = fake.MakeTestConfig(789, [], [])
    self.services.config.StoreConfig('cnxn', config)

    av_24 = tracker_pb2.ApprovalValue(
        approval_id=24, approver_ids=[111],
        status=tracker_pb2.ApprovalStatus.NOT_SET, set_on=1234, setter_id=999)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111,
                               issue_id=78901, approval_values=[av_24])
    self.services.issue.TestAddIssue(issue)

    delta = tracker_pb2.ApprovalDelta()
    with self.work_env as we:
      we.UpdateIssueApproval(
          78901, 24, delta, 'Another Desc', True, kept_attachments=[1, 2, 3])

    comments = self.services.issue.GetCommentsForIssue('cnxn', issue.issue_id)
    mockFilterKeptAttachments.assert_called_once_with(
        True, [1, 2, 3], comments, 24)
    self.services.issue.DeltaUpdateIssueApproval.assert_called_once_with(
        self.mr.cnxn, 111, config, issue, av_24, delta,
        comment_content='Another Desc', is_description=True,
        attachments=None, kept_attachments=[1, 2])

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testConvertIssueApprovalsTemplate(self, fake_pasicn):
    """We can convert an issue's approvals to match template's approvals."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    issue.approval_values = [
        tracker_pb2.ApprovalValue(
            approval_id=3,
            phase_id=4,
            status=tracker_pb2.ApprovalStatus.APPROVED,
            approver_ids=[111],
        ),
        tracker_pb2.ApprovalValue(
            approval_id=4,
            phase_id=5,
            approver_ids=[111]),
        tracker_pb2.ApprovalValue(approval_id=6)]
    issue.phases = [
        tracker_pb2.Phase(name='Expired', phase_id=4),
        tracker_pb2.Phase(name='canary', phase_id=3)]
    issue.field_values = [
        tracker_bizobj.MakeFieldValue(8, None, 'Pink', None, None, None, False),
        tracker_bizobj.MakeFieldValue(
            9, None, 'Silver', None, None, None, False, phase_id=3),
        tracker_bizobj.MakeFieldValue(
            19, None, 'Orange', None, None, None, False, phase_id=4),
        ]

    self.services.issue._UpdateIssuesApprovals = mock.Mock()
    self.SignIn()

    template = testing_helpers.DefaultTemplates()[0]
    template.approval_values = [
        tracker_pb2.ApprovalValue(
            approval_id=3,
            phase_id=6,  # Different phase. Nothing else affected.
            approver_ids=[222]),
        # No phase. Nothing else affected.
        tracker_pb2.ApprovalValue(approval_id=4),
        # New approval not already found in issue.
        tracker_pb2.ApprovalValue(
            approval_id=7,
            phase_id=5,
            approver_ids=[222]),
    ]  # No approval 6
    template.phases = [tracker_pb2.Phase(name='Canary', phase_id=5),
                       tracker_pb2.Phase(name='Stable-Exp', phase_id=6)]
    self.services.template.GetTemplateByName.return_value = template

    config = self.services.config.GetProjectConfig(self.cnxn, 789)
    config.approval_defs = [
        tracker_pb2.ApprovalDef(approval_id=3, survey='Question3'),
        tracker_pb2.ApprovalDef(approval_id=4, survey='Question4'),
        tracker_pb2.ApprovalDef(approval_id=7, survey='Question7'),
    ]
    config.field_defs = [
      tracker_pb2.FieldDef(
          field_id=3, project_id=789, field_name='Cow'),
      tracker_pb2.FieldDef(
          field_id=4, project_id=789, field_name='Chicken'),
      tracker_pb2.FieldDef(
          field_id=6, project_id=789, field_name='Llama'),
      tracker_pb2.FieldDef(
          field_id=7, project_id=789, field_name='Roo'),
      tracker_pb2.FieldDef(
          field_id=8, project_id=789, field_name='Salmon'),
      tracker_pb2.FieldDef(
          field_id=9, project_id=789, field_name='Tuna', is_phase_field=True),
      tracker_pb2.FieldDef(
          field_id=10, project_id=789, field_name='Clown', is_phase_field=True),
    ]
    self.work_env.ConvertIssueApprovalsTemplate(
        config, issue, 'template_name', 'Convert', send_email=False)

    expected_avs = [
      tracker_pb2.ApprovalValue(
            approval_id=3,
            phase_id=6,
            status=tracker_pb2.ApprovalStatus.APPROVED,
            approver_ids=[111],
        ),
      tracker_pb2.ApprovalValue(
          approval_id=4,
          approver_ids=[111]),
      tracker_pb2.ApprovalValue(
          approval_id=7,
          phase_id=5,
          approver_ids=[222]),
    ]
    expected_fvs = [
        tracker_bizobj.MakeFieldValue(8, None, 'Pink', None, None, None, False),
        tracker_bizobj.MakeFieldValue(
            9, None, 'Silver', None, None, None, False, phase_id=5),
    ]
    self.assertEqual(issue.approval_values, expected_avs)
    self.assertEqual(issue.field_values, expected_fvs)
    self.assertEqual(issue.phases, template.phases)
    self.services.template.GetTemplateByName.assert_called_once_with(
        self.mr.cnxn, 'template_name', 789)
    fake_pasicn.assert_called_with(
        issue.issue_id, 'testing-app.appspot.com', 111, send_email=False,
        comment_id=mock.ANY)

  def testConvertIssueApprovalsTemplate_NoSuchTemplate(self):
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.template.GetTemplateByName.return_value = None
    config = self.services.config.GetProjectConfig(self.cnxn, 789)
    with self.assertRaises(exceptions.NoSuchTemplateException):
      self.work_env.ConvertIssueApprovalsTemplate(
          config, issue, 'template_name', 'comment')

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testUpdateIssue_Normal(self, fake_pasicn):
    """We can update an issue."""
    self.SignIn()
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 0)
    self.services.issue.TestAddIssue(issue)
    delta = tracker_pb2.IssueDelta(
        owner_id=111, summary='New summary', cc_ids_add=[333])

    with self.work_env as we:
      we.UpdateIssue(issue, delta, 'Getting started')

    self.assertEqual(111, issue.owner_id)
    self.assertEqual('New summary', issue.summary)
    self.assertEqual([333], issue.cc_ids)
    self.assertEqual([issue.issue_id], self.services.issue.enqueued_issues)
    comments = self.services.issue.GetCommentsForIssue('cnxn', issue.issue_id)
    comment_pb = comments[-1]
    self.assertFalse(comment_pb.is_description)
    fake_pasicn.assert_called_with(
        issue.issue_id, 'testing-app.appspot.com', 111, send_email=True,
        old_owner_id=0, comment_id=comment_pb.id)

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testUpdateIssue_EditDescription(self, fake_pasicn):
    """We can edit an issue description."""
    self.SignIn()
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111)
    self.services.issue.TestAddIssue(issue)
    delta = tracker_pb2.IssueDelta()

    with self.work_env as we:
      we.UpdateIssue(issue, delta, 'New description', is_description=True)

    comments = self.services.issue.GetCommentsForIssue('cnxn', issue.issue_id)
    comment_pb = comments[-1]
    self.assertTrue(comment_pb.is_description)
    fake_pasicn.assert_called_with(
        issue.issue_id, 'testing-app.appspot.com', 111, send_email=True,
        old_owner_id=111, comment_id=comment_pb.id)

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testUpdateIssue_NotAllowedToEditDescription(self, fake_pasicn):
    """We cannot edit an issue description without EditIssue permission."""
    self.SignIn(222)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111)
    self.services.issue.TestAddIssue(issue)
    delta = tracker_pb2.IssueDelta()

    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.UpdateIssue(issue, delta, 'New description', is_description=True)

    fake_pasicn.assert_not_called()

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testUpdateIssue_AddComment(self, fake_pasicn):
    """We can add a comment."""
    self.SignIn(222)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111)
    self.services.issue.TestAddIssue(issue)
    delta = tracker_pb2.IssueDelta()

    with self.work_env as we:
      we.UpdateIssue(issue, delta, 'New description')

    comments = self.services.issue.GetCommentsForIssue('cnxn', issue.issue_id)
    comment_pb = comments[-1]
    self.assertFalse(comment_pb.is_description)
    fake_pasicn.assert_called_with(
        issue.issue_id, 'testing-app.appspot.com', 222, send_email=True,
        old_owner_id=111, comment_id=comment_pb.id)

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  @mock.patch('framework.permissions.GetExtraPerms')
  def testUpdateIssue_EditOwner(self, fake_extra_perms, fake_pasicn):
    """We can edit the owner with the EditIssueOwner permission."""
    self.SignIn(222)
    fake_extra_perms.return_value = [permissions.EDIT_ISSUE_OWNER]
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111)
    self.services.issue.TestAddIssue(issue)
    delta = tracker_pb2.IssueDelta(owner_id=0)

    with self.work_env as we:
      we.UpdateIssue(issue, delta, '')

    comments = self.services.issue.GetCommentsForIssue('cnxn', issue.issue_id)
    comment_pb = comments[-1]
    self.assertFalse(comment_pb.is_description)
    self.assertEqual(0, issue.owner_id)
    fake_pasicn.assert_called_with(
        issue.issue_id, 'testing-app.appspot.com', 222, send_email=True,
        old_owner_id=111, comment_id=comment_pb.id)

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  @mock.patch('framework.permissions.GetExtraPerms')
  def testUpdateIssue_EditSummary(self, fake_extra_perms, fake_pasicn):
    """We can edit the owner with the EditIssueOwner permission."""
    self.SignIn(222)
    fake_extra_perms.return_value = [permissions.EDIT_ISSUE_SUMMARY]
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111)
    self.services.issue.TestAddIssue(issue)
    delta = tracker_pb2.IssueDelta(summary='New Summary')

    with self.work_env as we:
      we.UpdateIssue(issue, delta, '')

    comments = self.services.issue.GetCommentsForIssue('cnxn', issue.issue_id)
    comment_pb = comments[-1]
    self.assertFalse(comment_pb.is_description)
    self.assertEqual('New Summary', issue.summary)
    fake_pasicn.assert_called_with(
        issue.issue_id, 'testing-app.appspot.com', 222, send_email=True,
        old_owner_id=111, comment_id=comment_pb.id)

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  @mock.patch('framework.permissions.GetExtraPerms')
  def testUpdateIssue_EditStatus(self, fake_extra_perms, fake_pasicn):
    """We can edit the owner with the EditIssueOwner permission."""
    self.SignIn(222)
    fake_extra_perms.return_value = [permissions.EDIT_ISSUE_STATUS]
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111)
    self.services.issue.TestAddIssue(issue)
    delta = tracker_pb2.IssueDelta(status='Fixed')

    with self.work_env as we:
      we.UpdateIssue(issue, delta, '')

    comments = self.services.issue.GetCommentsForIssue('cnxn', issue.issue_id)
    comment_pb = comments[-1]
    self.assertFalse(comment_pb.is_description)
    self.assertEqual('Fixed', issue.status)
    fake_pasicn.assert_called_with(
        issue.issue_id, 'testing-app.appspot.com', 222, send_email=True,
        old_owner_id=111, comment_id=comment_pb.id)

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  @mock.patch('framework.permissions.GetExtraPerms')
  def testUpdateIssue_EditCC(self, fake_extra_perms, _fake_pasicn):
    """We can edit the owner with the EditIssueOwner permission."""
    self.SignIn(222)
    fake_extra_perms.return_value = [permissions.EDIT_ISSUE_CC]
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111)
    issue.cc_ids = [111]
    self.services.issue.TestAddIssue(issue)
    delta = tracker_pb2.IssueDelta(cc_ids_add=[222])

    with self.work_env as we:
      we.UpdateIssue(issue, delta, '')

    self.assertEqual([111, 222], issue.cc_ids)
    delta = tracker_pb2.IssueDelta(cc_ids_remove=[111])

    with self.work_env as we:
      we.UpdateIssue(issue, delta, '')

    self.assertEqual([222], issue.cc_ids)

  def testUpdateIssue_BadOwner(self):
    """We reject new issue owners that don't pass validation."""
    self.SignIn()
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111)
    self.services.issue.TestAddIssue(issue)

    # No such user ID.
    delta = tracker_pb2.IssueDelta(owner_id=555)
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException) as cm:
        we.UpdateIssue(issue, delta, '')
    self.assertEqual('Issue owner user ID not found',
                     cm.exception.message)

    # Not a member
    delta = tracker_pb2.IssueDelta(owner_id=222)
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException) as cm:
        we.UpdateIssue(issue, delta, '')
    self.assertEqual('Issue owner must be a project member',
                     cm.exception.message)

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testUpdateIssue_MergeInto(self, _fake_pasicn):
    self.SignIn()
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111)
    issue2 = fake.MakeTestIssue(789, 2, 'summary2', 'Available', 111)
    self.services.issue.TestAddIssue(issue)
    self.services.issue.TestAddIssue(issue2)
    delta = tracker_pb2.IssueDelta(
        merged_into=issue2.issue_id,
        status='Duplicate')

    issue.cc_ids = [111, 222, 333, 444]
    with self.work_env as we:
      we.UpdateIssue(issue, delta, '')

    comments = self.services.issue.GetCommentsForIssue('cnxn', issue2.issue_id)

    # Original issue marked as duplicate.
    self.assertEqual('Duplicate', issue.status)
    # Target issue has original issue's CCs.
    self.assertEqual([444, 333, 222, 111], issue2.cc_ids)
    # A comment was added to the target issue.
    self.assertEqual(
        'Issue 1 has been merged into this issue.',
        comments[-1].content)

  def testUpdateIssue_MergeIntoRestrictedIssue(self):
    """We cannot merge into an issue we cannot view and edit."""
    self.SignIn(333)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111)
    issue2 = fake.MakeTestIssue(789, 2, 'summary2', 'Available', 111)
    self.services.issue.TestAddIssue(issue)
    self.services.issue.TestAddIssue(issue2)

    delta = tracker_pb2.IssueDelta(
        merged_into=issue2.issue_id,
        status='Duplicate')

    issue2.labels = ['Restrict-View-Foo']
    with self.work_env as we:
      with self.assertRaises(permissions.PermissionException):
        we.UpdateIssue(issue, delta, '')

    issue2.labels = ['Restrict-EditIssue-Foo']
    with self.work_env as we:
      with self.assertRaises(permissions.PermissionException):
        we.UpdateIssue(issue, delta, '')

    # Original issue still available.
    self.assertEqual('Available', issue.status)
    # Target issue was not modified.
    self.assertEqual([], issue2.cc_ids)
    # No comment was added.
    comments = self.services.issue.GetCommentsForIssue('cnxn', issue2.issue_id)
    self.assertEqual(1, len(comments))

  def testUpdateIssue_MergeIntoItself(self):
    """We cannot merge an issue into itself."""
    self.SignIn()
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111)
    self.services.issue.TestAddIssue(issue)
    delta = tracker_pb2.IssueDelta(
        merged_into=issue.issue_id,
        status='Duplicate')

    with self.work_env as we:
      with self.assertRaises(exceptions.InputException) as cm:
        we.UpdateIssue(issue, delta, '')
    self.assertEqual('Cannot merge an issue into itself.', cm.exception.message)

    # Original issue still available.
    self.assertEqual('Available', issue.status)
    # No comment was added.
    comments = self.services.issue.GetCommentsForIssue('cnxn', issue.issue_id)
    self.assertEqual(1, len(comments))

  def testUpdateIssue_BlockOnItself(self):
    """We cannot block an issue on itself."""
    self.SignIn()
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111)
    self.services.issue.TestAddIssue(issue)

    delta = tracker_pb2.IssueDelta(blocked_on_add=[issue.issue_id])
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException) as cm:
        we.UpdateIssue(issue, delta, '')
    self.assertEqual('Cannot block an issue on itself.', cm.exception.message)

    delta = tracker_pb2.IssueDelta(blocking_add=[issue.issue_id])
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException) as cm:
        we.UpdateIssue(issue, delta, '')
    self.assertEqual('Cannot block an issue on itself.', cm.exception.message)

    # Original issue was not modified.
    self.assertEqual(0, len(issue.blocked_on_iids))
    self.assertEqual(0, len(issue.blocking_iids))
    # No comment was added.
    comments = self.services.issue.GetCommentsForIssue('cnxn', issue.issue_id)
    self.assertEqual(1, len(comments))

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testUpdateIssue_Attachments(self, fake_pasicn):
    """We can attach files as we make a change."""
    self.SignIn()
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 0)
    self.services.issue.TestAddIssue(issue)
    delta = tracker_pb2.IssueDelta(
        owner_id=111, summary='New summary', cc_ids_add=[333])

    attachments = []
    with self.work_env as we:
      we.UpdateIssue(issue, delta, 'Getting started', attachments=attachments)

    self.assertEqual(111, issue.owner_id)
    self.assertEqual('New summary', issue.summary)
    self.assertEqual([333], issue.cc_ids)
    self.assertEqual([issue.issue_id], self.services.issue.enqueued_issues)

    comments = self.services.issue.GetCommentsForIssue('cnxn', issue.issue_id)
    comment_pb = comments[-1]
    self.assertEqual([], comment_pb.attachments)
    fake_pasicn.assert_called_with(
        issue.issue_id, 'testing-app.appspot.com', 111, send_email=True,
        old_owner_id=0, comment_id=comment_pb.id)

    attachments = [
        ('README.md', 'readme content', 'text/plain'),
        ('hello.txt', 'hello content', 'text/plain')]
    with self.work_env as we:
      we.UpdateIssue(issue, delta, 'Getting started', attachments=attachments)
    comments = self.services.issue.GetCommentsForIssue('cnxn', issue.issue_id)
    comment_pb = comments[-1]
    self.assertEqual(2, len(comment_pb.attachments))

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testUpdateIssue_KeptAttachments(self, _fake_pasicn):
    """We can attach files as we make a change."""
    self.SignIn()
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 111)
    self.services.issue.TestAddIssue(issue)

    # Add some initial attachments
    delta = tracker_pb2.IssueDelta()
    attachments = [
        ('README.md', 'readme content', 'text/plain'),
        ('hello.txt', 'hello content', 'text/plain')]
    with self.work_env as we:
      we.UpdateIssue(
          issue, delta, 'New Description', attachments=attachments,
          is_description=True)

    with self.work_env as we:
      we.UpdateIssue(
          issue, delta, 'Yet Another Description', is_description=True,
          kept_attachments=[1, 2, 3])

    comments = self.services.issue.GetCommentsForIssue('cnxn', issue.issue_id)
    comment_pb = comments[-1]
    self.assertEqual(1, len(comment_pb.attachments))
    self.assertEqual('hello.txt', comment_pb.attachments[0].filename)

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testUpdateIssue_PermissionDenied(self, fake_pasicn):
    """We reject attempts to update an issue when the user lacks permission."""
    issue = fake.MakeTestIssue(789, 1, 'summary', 'Available', 555)
    self.services.issue.TestAddIssue(issue)
    delta = tracker_pb2.IssueDelta(
        owner_id=222, summary='New summary', cc_ids_add=[333])

    with self.work_env as we:
      # User is not signed in.
      with self.assertRaises(permissions.PermissionException):
        we.UpdateIssue(issue, delta, 'I am anon')

      # User signed in to acconut that can view but not edit.
      self.SignIn(user_id=222)
      with self.assertRaises(permissions.PermissionException):
        we.UpdateIssue(issue, delta, 'I am not a project member')

      # User signed in to acconut that can view and edit, but issue
      # restricts edits to a perm that the user lacks.
      self.SignIn(user_id=111)
      issue.labels.append('Restrict-EditIssue-CoreTeam')
      with self.assertRaises(permissions.PermissionException):
        we.UpdateIssue(issue, delta, 'I lack CoreTeam')

    fake_pasicn.assert_not_called()

  def testDeleteIssue(self):
    """We can mark and unmark an issue as deleted."""
    self.SignIn(user_id=self.admin_user.user_id)
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    with self.work_env as we:
      _actual = we.DeleteIssue(issue, True)
    self.assertTrue(issue.deleted)
    with self.work_env as we:
      _actual = we.DeleteIssue(issue, False)
    self.assertFalse(issue.deleted)

  def testFlagIssue_Normal(self):
    """Users can mark and unmark an issue as spam."""
    self.services.user.TestAddUser('user222@example.com', 222)
    self.SignIn(user_id=222)
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    with self.work_env as we:
      we.FlagIssues([issue], True)
    self.assertEqual(
        [222], self.services.spam.reports_by_issue_id[78901])
    self.assertNotIn(
        222, self.services.spam.manual_verdicts_by_issue_id[78901])
    with self.work_env as we:
      we.FlagIssues([issue], False)
    self.assertEqual(
        [], self.services.spam.reports_by_issue_id[78901])
    self.assertNotIn(
        222, self.services.spam.manual_verdicts_by_issue_id[78901])

  def testFlagIssue_AutoVerdict(self):
    """Admins can mark and unmark an issue as spam and it counts as verdict."""
    self.SignIn(user_id=self.admin_user.user_id)
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    with self.work_env as we:
      we.FlagIssues([issue], True)
    self.assertEqual(
        [444], self.services.spam.reports_by_issue_id[78901])
    self.assertTrue(self.services.spam.manual_verdicts_by_issue_id[78901][444])
    with self.work_env as we:
      we.FlagIssues([issue], False)
    self.assertEqual(
        [], self.services.spam.reports_by_issue_id[78901])
    self.assertFalse(
        self.services.spam.manual_verdicts_by_issue_id[78901][444])

  def testFlagIssue_NotAllowed(self):
    """Anons can't mark issues as spam."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)

    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.FlagIssues([issue], True)

    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.FlagIssues([issue], False)

  def testLookupIssuesFlaggers_Normal(self):
    issue_1 = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue_1)
    comment_1_1 = tracker_pb2.IssueComment(
        project_id=789, content='lorem ipsum', user_id=111,
        issue_id=issue_1.issue_id)
    comment_1_2 = tracker_pb2.IssueComment(
        project_id=789, content='dolor sit amet', user_id=111,
        issue_id=issue_1.issue_id)
    self.services.issue.TestAddComment(comment_1_1, 1)
    self.services.issue.TestAddComment(comment_1_2, 1)

    issue_2 = fake.MakeTestIssue(789, 2, 'sum', 'New', 111, issue_id=78902)
    self.services.issue.TestAddIssue(issue_2)
    comment_2_1 = tracker_pb2.IssueComment(
        project_id=789, content='lorem ipsum', user_id=111,
        issue_id=issue_2.issue_id)
    self.services.issue.TestAddComment(comment_2_1, 2)


    self.SignIn(user_id=222)
    with self.work_env as we:
      we.FlagIssues([issue_1], True)

    self.SignIn(user_id=111)
    with self.work_env as we:
      we.FlagComment(issue_1, comment_1_2, True)
      we.FlagComment(issue_2, comment_2_1, True)

      reporters = we.LookupIssuesFlaggers([issue_1, issue_2])
      self.assertEqual({
          issue_1.issue_id: ([222], {comment_1_2.id: [111]}),
          issue_2.issue_id: ([], {comment_2_1.id: [111]}),
      }, reporters)

  def testLookupIssueFlaggers_Normal(self):
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    comment_1 = tracker_pb2.IssueComment(
        project_id=789, content='lorem ipsum', user_id=111,
        issue_id=issue.issue_id)
    comment_2 = tracker_pb2.IssueComment(
        project_id=789, content='dolor sit amet', user_id=111,
        issue_id=issue.issue_id)
    self.services.issue.TestAddComment(comment_1, 1)
    self.services.issue.TestAddComment(comment_2, 2)

    self.SignIn(user_id=222)
    with self.work_env as we:
      we.FlagIssues([issue], True)

    self.SignIn(user_id=111)
    with self.work_env as we:
      we.FlagComment(issue, comment_2, True)
      issue_reporters, comment_reporters = we.LookupIssueFlaggers(issue)
      self.assertEqual([222], issue_reporters)
      self.assertEqual({comment_2.id: [111]}, comment_reporters)

  def testRerankBlockedOnIssues_SplitBelow(self):
    parent_issue = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, project_name='proj', issue_id=1001)
    self.services.issue.TestAddIssue(parent_issue)

    issues = []
    for idx in range(2, 6):
      issues.append(fake.MakeTestIssue(
          789, idx, 'sum', 'New', 111, project_name='proj', issue_id=1000+idx))
      self.services.issue.TestAddIssue(issues[-1])
      parent_issue.blocked_on_iids.append(issues[-1].issue_id)
      next_rank = sys.maxint
      if parent_issue.blocked_on_ranks:
        next_rank = parent_issue.blocked_on_ranks[-1] - 1
      parent_issue.blocked_on_ranks.append(next_rank)

    self.SignIn()
    with self.work_env as we:
      we.RerankBlockedOnIssues(parent_issue, 1002, 1004, False)
      new_parent_issue = we.GetIssue(1001)

    self.assertEqual([1003, 1004, 1002, 1005], new_parent_issue.blocked_on_iids)

  def testRerankBlockedOnIssues_SplitAbove(self):
    parent_issue = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, project_name='proj', issue_id=1001)
    self.services.issue.TestAddIssue(parent_issue)

    issues = []
    for idx in range(2, 6):
      issues.append(fake.MakeTestIssue(
          789, idx, 'sum', 'New', 111, project_name='proj', issue_id=1000+idx))
      self.services.issue.TestAddIssue(issues[-1])
      parent_issue.blocked_on_iids.append(issues[-1].issue_id)
      next_rank = sys.maxint
      if parent_issue.blocked_on_ranks:
        next_rank = parent_issue.blocked_on_ranks[-1] - 1
      parent_issue.blocked_on_ranks.append(next_rank)

    self.SignIn()
    with self.work_env as we:
      we.RerankBlockedOnIssues(parent_issue, 1002, 1004, True)
      new_parent_issue = we.GetIssue(1001)

    self.assertEqual([1003, 1002, 1004, 1005], new_parent_issue.blocked_on_iids)

  @mock.patch('tracker.rerank_helpers.MAX_RANKING', 1)
  def testRerankBlockedOnIssues_NoRoom(self):
    parent_issue = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, project_name='proj', issue_id=1001)
    parent_issue.blocked_on_ranks = [1, 0, 0]
    self.services.issue.TestAddIssue(parent_issue)

    issues = []
    for idx in range(2, 5):
      issues.append(fake.MakeTestIssue(
          789, idx, 'sum', 'New', 111, project_name='proj', issue_id=1000+idx))
      self.services.issue.TestAddIssue(issues[-1])
      parent_issue.blocked_on_iids.append(issues[-1].issue_id)

    self.SignIn()
    with self.work_env as we:
      we.RerankBlockedOnIssues(parent_issue, 1003, 1004, True)
      new_parent_issue = we.GetIssue(1001)

    self.assertEqual([1002, 1003, 1004], new_parent_issue.blocked_on_iids)

  def testRerankBlockedOnIssues_CantEditIssue(self):
    parent_issue = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 555, project_name='proj', issue_id=1001)
    parent_issue.labels = ['Restrict-EditIssue-Foo']
    self.services.issue.TestAddIssue(parent_issue)

    self.SignIn()
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.RerankBlockedOnIssues(parent_issue, 1003, 1002, True)

  def testRerankBlockedOnIssues_MovedNotOnBlockedOn(self):
    parent_issue = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, project_name='proj', issue_id=1001)
    self.services.issue.TestAddIssue(parent_issue)

    self.SignIn()
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.RerankBlockedOnIssues(parent_issue, 1003, 1002, True)

  def testRerankBlockedOnIssues_TargetNotOnBlockedOn(self):
    moved = fake.MakeTestIssue(
        789, 2, 'sum', 'New', 111, project_name='proj', issue_id=1002)
    self.services.issue.TestAddIssue(moved)
    parent_issue = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, project_name='proj', issue_id=1001)
    parent_issue.blocked_on_iids = [1002]
    parent_issue.blocked_on_ranks = [1]
    self.services.issue.TestAddIssue(parent_issue)

    self.SignIn()
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.RerankBlockedOnIssues(parent_issue, 1002, 1003, True)

  # FUTURE: GetIssuePermissionsForUser()

  # FUTURE: CreateComment()

  def testGetIssueComments_Normal(self):
    """We can get an existing issue by project_id and local_id."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    comment = tracker_pb2.IssueComment(
        project_id=789, content='more info', user_id=111,
        issue_id=issue.issue_id)
    self.services.issue.TestAddComment(comment, 1)

    with self.work_env as we:
      actual_comments = we.ListIssueComments(issue)

    self.assertEqual(2, len(actual_comments))
    self.assertEqual('sum', actual_comments[0].content)
    self.assertEqual('more info', actual_comments[1].content)

  # FUTURE: UpdateComment()

  def testDeleteComment_Normal(self):
    """We can mark and unmark a comment as deleted."""
    self.SignIn(user_id=111)
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    comment = tracker_pb2.IssueComment(
        project_id=789, content='soon to be deleted', user_id=111,
        issue_id=issue.issue_id)
    self.services.issue.TestAddComment(comment, 1)
    with self.work_env as we:
      we.DeleteComment(issue, comment, True)
      self.assertEqual(111, comment.deleted_by)
      we.DeleteComment(issue, comment, False)
      self.assertEqual(None, comment.deleted_by)

  @mock.patch('services.issue_svc.IssueService.SoftDeleteComment')
  def testDeleteComment_UndeleteableSpam(self, mockSoftDeleteComment):
    """Throws exception when comment is spam and owner is deleting."""
    self.SignIn(user_id=111)
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    comment = tracker_pb2.IssueComment(
        project_id=789, content='soon to be deleted', user_id=111,
        issue_id=issue.issue_id, is_spam=True)
    self.services.issue.TestAddComment(comment, 1)
    with self.work_env as we:
      with self.assertRaises(permissions.PermissionException):
        we.DeleteComment(issue, comment, True)
      self.assertEqual(None, comment.deleted_by)
      mockSoftDeleteComment.assert_not_called()

  @mock.patch('services.issue_svc.IssueService.SoftDeleteComment')
  @mock.patch('framework.permissions.CanDeleteComment')
  def testDeleteComment_UndeletablePermissions(self, mockCanDelete,
                                               mockSoftDeleteComment):
    """Throws exception when deleter doesn't have permission to do so."""
    mockCanDelete.return_value = False
    self.SignIn(user_id=111)
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    comment = tracker_pb2.IssueComment(
        project_id=789, content='soon to be deleted', user_id=111,
        issue_id=issue.issue_id, is_spam=True)
    self.services.issue.TestAddComment(comment, 1)
    with self.work_env as we:
      with self.assertRaises(permissions.PermissionException):
        we.DeleteComment(issue, comment, True)
      self.assertEqual(None, comment.deleted_by)
      mockSoftDeleteComment.assert_not_called()

  def testDeleteAttachment_Normal(self):
    """We can mark and unmark a comment attachment as deleted."""
    self.SignIn(user_id=111)
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    comment = tracker_pb2.IssueComment(
        project_id=789, content='soon to be deleted', user_id=111,
        issue_id=issue.issue_id)
    self.services.issue.TestAddComment(comment, 1)
    attachment = tracker_pb2.Attachment()
    self.services.issue.TestAddAttachment(attachment, comment.id, 1)
    with self.work_env as we:
      we.DeleteAttachment(
          issue, comment, attachment.attachment_id, True)
      self.assertTrue(attachment.deleted)
      we.DeleteAttachment(
          issue, comment, attachment.attachment_id, False)
      self.assertFalse(attachment.deleted)

  @mock.patch('services.issue_svc.IssueService.SoftDeleteComment')
  @mock.patch('framework.permissions.CanDeleteComment')
  def testDeleteAttachment_UndeletablePermissions(
      self, mockCanDelete, mockSoftDeleteComment):
    """Throws exception when deleter doesn't have permission to do so."""
    mockCanDelete.return_value = False
    self.SignIn(user_id=111)
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    comment = tracker_pb2.IssueComment(
        project_id=789, content='soon to be deleted', user_id=111,
        issue_id=issue.issue_id, is_spam=True)
    self.services.issue.TestAddComment(comment, 1)
    attachment = tracker_pb2.Attachment()
    self.services.issue.TestAddAttachment(attachment, comment.id, 1)
    self.assertFalse(attachment.deleted)
    with self.work_env as we:
      with self.assertRaises(permissions.PermissionException):
        we.DeleteAttachment(
            issue, comment, attachment.attachment_id, True)
      self.assertFalse(attachment.deleted)
      mockSoftDeleteComment.assert_not_called()

  def testFlagComment_Normal(self):
    """We can mark and unmark a comment as spam."""
    self.SignIn(user_id=111)
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    comment = tracker_pb2.IssueComment(
        project_id=789, content='soon to be deleted', user_id=111,
        issue_id=issue.issue_id)
    self.services.issue.TestAddComment(comment, 1)

    comment_reports = self.services.spam.comment_reports_by_issue_id
    with self.work_env as we:
      we.FlagComment(issue, comment, True)
      self.assertEqual([111], comment_reports[issue.issue_id][comment.id])
      we.FlagComment(issue, comment, False)
      self.assertEqual([], comment_reports[issue.issue_id][comment.id])

  def testFlagComment_AutoVerdict(self):
    """Admins can mark and unmark a comment as spam, and it is a verdict."""
    self.SignIn(user_id=self.admin_user.user_id)
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    comment = tracker_pb2.IssueComment(
        project_id=789, content='soon to be deleted', user_id=111,
        issue_id=issue.issue_id)
    self.services.issue.TestAddComment(comment, 1)

    comment_reports = self.services.spam.comment_reports_by_issue_id
    manual_verdicts = self.services.spam.manual_verdicts_by_comment_id
    with self.work_env as we:
      we.FlagComment(issue, comment, True)
      self.assertEqual([444], comment_reports[issue.issue_id][comment.id])
      self.assertTrue(manual_verdicts[comment.id][444])
      we.FlagComment(issue, comment, False)
      self.assertEqual([], comment_reports[issue.issue_id][comment.id])
      self.assertFalse(manual_verdicts[comment.id][444])

  def testFlagComment_NotAllowed(self):
    """Anons can't mark comment as spam."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    comment = tracker_pb2.IssueComment(
        project_id=789, content='soon to be deleted', user_id=111,
        issue_id=issue.issue_id)
    self.services.issue.TestAddComment(comment, 1)

    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.FlagComment(issue, comment, True)

    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.FlagComment(issue, comment, False)

  def testStarIssue_Normal(self):
    """We can star and unstar issues."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    self.SignIn(user_id=111)

    with self.work_env as we:
      we.StarIssue(issue, True)
      self.assertEqual(1, issue.star_count)
      we.StarIssue(issue, False)
      self.assertEqual(0, issue.star_count)

  def testStarIssue_Anon(self):
    """A signed out user cannot star or unstar issues."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    # Don't sign in.

    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.StarIssue(issue, True)

  def testIsIssueStarred_Normal(self):
    """We can check if the current user starred an issue or not."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    self.SignIn(user_id=111)

    with self.work_env as we:
      self.assertFalse(we.IsIssueStarred(issue))
      we.StarIssue(issue, True)
      self.assertTrue(we.IsIssueStarred(issue))
      we.StarIssue(issue, False)
      self.assertFalse(we.IsIssueStarred(issue))

  def testIsIssueStarred_Anon(self):
    """A signed out user has never starred anything."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    # Don't sign in.

    with self.work_env as we:
      self.assertFalse(we.IsIssueStarred(issue))

  def testListStarredIssueIDs_Anon(self):
    """A signed out users has no starred issues."""
    # Don't sign in.
    with self.work_env as we:
      self.assertEqual([], we.ListStarredIssueIDs())

  def testListStarredIssueIDs_Normal(self):
    """We can get the list of issues starred by a user."""
    issue1 = fake.MakeTestIssue(789, 1, 'sum1', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue1)
    issue2 = fake.MakeTestIssue(789, 2, 'sum2', 'New', 111, issue_id=78902)
    self.services.issue.TestAddIssue(issue2)

    self.SignIn(user_id=111)
    with self.work_env as we:
      # User has not starred anything yet.
      self.assertEqual([], we.ListStarredIssueIDs())

      # Now, star a couple of issues.
      we.StarIssue(issue1, True)
      we.StarIssue(issue2, True)
      self.assertItemsEqual(
          [issue1.issue_id, issue2.issue_id],
          we.ListStarredIssueIDs())

    # Check that there is no cross-talk between users.
    self.SignIn(user_id=222)
    with self.work_env as we:
      # User has not starred anything yet.
      self.assertEqual([], we.ListStarredIssueIDs())

      # Now, star an issue as that other user.
      we.StarIssue(issue1, True)
      self.assertEqual([issue1.issue_id], we.ListStarredIssueIDs())

  def testGetUser(self):
    """We return the User PB for the given existing user id."""
    expected = self.services.user.TestAddUser('test5@example.com', 555)
    with self.work_env as we:
      actual = we.GetUser(555)
      self.assertEqual(expected, actual)

  def testGetUser_DoesntExist(self):
    """We reject attempts to get an user that doesn't exist."""
    with self.assertRaises(exceptions.NoSuchUserException):
      with self.work_env as we:
        we.GetUser(555)

  def setUpUserGroups(self):
    self.services.user.TestAddUser('test5@example.com', 555)
    self.services.user.TestAddUser('test6@example.com', 666)
    public_group_id = self.services.usergroup.CreateGroup(
        self.cnxn, self.services, 'group1@test.com', 'anyone')
    private_group_id = self.services.usergroup.CreateGroup(
        self.cnxn, self.services, 'group2@test.com', 'owners')
    self.services.usergroup.UpdateMembers(
        self.cnxn, public_group_id, [111], 'member')
    self.services.usergroup.UpdateMembers(
        self.cnxn, private_group_id, [555, 111], 'owner')
    return public_group_id, private_group_id

  def testGetMemberships_Anon(self):
    """We return groups the user is in and that are visible to the requester."""
    public_group_id, _ = self.setUpUserGroups()
    with self.work_env as we:
      self.assertEqual(we.GetMemberships(111), [public_group_id])

  def testGetMemberships_UserHasPerm(self):
    public_group_id, private_group_id = self.setUpUserGroups()
    self.SignIn(user_id=555)
    with self.work_env as we:
      self.assertItemsEqual(
          we.GetMemberships(111), [public_group_id, private_group_id])

  def testGetMemeberships_UserHasNoPerm(self):
    public_group_id, _ = self.setUpUserGroups()
    self.SignIn(user_id=666)
    with self.work_env as we:
      self.assertItemsEqual(
          we.GetMemberships(111), [public_group_id])

  def testGetMemeberships_GetOwnMembership(self):
    public_group_id, private_group_id = self.setUpUserGroups()
    self.SignIn(user_id=111)
    with self.work_env as we:
      self.assertItemsEqual(
          we.GetMemberships(111), [public_group_id, private_group_id])

  def testListReferencedUsers(self):
    """We return the list of User PBs for the given existing user emails."""
    user5 = self.services.user.TestAddUser('test5@example.com', 555)
    user6 = self.services.user.TestAddUser('test6@example.com', 666)
    with self.work_env as we:
      # We ignore emails that are empty or belong to non-existent users.
      users, linked_user_ids = we.ListReferencedUsers(
          ['test4@example.com', 'test5@example.com', 'test6@example.com', ''])
      self.assertItemsEqual(users, [user5, user6])
      self.assertEqual(linked_user_ids, [])

  def testListReferencedUsers_Linked(self):
    """We return User PBs and the IDs of any linked accounts."""
    user5 = self.services.user.TestAddUser('test5@example.com', 555)
    user5.linked_child_ids = [666, 777]
    user6 = self.services.user.TestAddUser('test6@example.com', 666)
    user6.linked_parent_id = 555
    with self.work_env as we:
      # We ignore emails that are empty or belong to non-existent users.
      users, linked_user_ids = we.ListReferencedUsers(
          ['test4@example.com', 'test5@example.com', 'test6@example.com', ''])
      self.assertItemsEqual(users, [user5, user6])
      self.assertItemsEqual(linked_user_ids, [555, 666, 777])

  def testStarUser_Normal(self):
    """We can star and unstar a user."""
    self.SignIn()
    with self.work_env as we:
      self.assertFalse(we.IsUserStarred(111))
      we.StarUser(111, True)
      self.assertTrue(we.IsUserStarred(111))
      we.StarUser(111, False)
      self.assertFalse(we.IsUserStarred(111))

  def testStarUser_NoSuchUser(self):
    """We can't star a nonexistent user."""
    self.SignIn()
    with self.assertRaises(exceptions.NoSuchUserException):
      with self.work_env as we:
        we.StarUser(999, True)

  def testStarUser_Anon(self):
    """Anon user can't star a user."""
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.StarUser(111, True)

  def testIsUserStarred_Normal(self):
    """We can check if a user is starred."""
    # Tested by method testStarUser_Normal().
    pass

  def testIsUserStarred_NoUserSpecified(self):
    """A user ID must be specified."""
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException):
        self.assertFalse(we.IsUserStarred(None))

  def testIsUserStarred_NoSuchUser(self):
    """We can't check for stars on a nonexistent user."""
    self.SignIn()
    with self.assertRaises(exceptions.NoSuchUserException):
      with self.work_env as we:
        we.IsUserStarred(999)

  def testGetUserStarCount_Normal(self):
    """We can count the stars of a user."""
    self.SignIn()
    with self.work_env as we:
      self.assertEqual(0, we.GetUserStarCount(111))
      we.StarUser(111, True)
      self.assertEqual(1, we.GetUserStarCount(111))

    self.SignIn(user_id=self.admin_user.user_id)
    with self.work_env as we:
      we.StarUser(111, True)
      self.assertEqual(2, we.GetUserStarCount(111))
      we.StarUser(111, False)
      self.assertEqual(1, we.GetUserStarCount(111))

  def testGetUserStarCount_NoSuchUser(self):
    """We can't count stars of a nonexistent user."""
    self.SignIn()
    with self.assertRaises(exceptions.NoSuchUserException):
      with self.work_env as we:
        we.GetUserStarCount(111111)

  def testGetUserStarCount_NoUserSpecified(self):
    """A user ID must be specified."""
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException):
        self.assertFalse(we.GetUserStarCount(None))

  def testGetPendingLinkInvites_Anon(self):
    """Anon never had pending linkage invites."""
    with self.work_env as we:
      as_parent, as_child = we.GetPendingLinkedInvites()
    self.assertEqual([], as_parent)
    self.assertEqual([], as_child)

  def testGetPendingLinkInvites_None(self):
    """When an account has no invites, we see empty lists."""
    self.SignIn()
    with self.work_env as we:
      as_parent, as_child = we.GetPendingLinkedInvites()
    self.assertEqual([], as_parent)
    self.assertEqual([], as_child)

  def testGetPendingLinkInvites_Some(self):
    """If there are any pending invites for the current user, we get them."""
    self.SignIn()
    self.services.user.invite_rows = [(111, 222), (333, 444), (555, 111)]
    with self.work_env as we:
      as_parent, as_child = we.GetPendingLinkedInvites()
    self.assertEqual([222], as_parent)
    self.assertEqual([555], as_child)

  def testInviteLinkedParent_MissingParent(self):
    """Invited parent must be specified by email."""
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException):
        we.InviteLinkedParent('')

  def testInviteLinkedParent_Anon(self):
    """Anon cannot invite anyone to link accounts."""
    with self.work_env as we:
      with self.assertRaises(permissions.PermissionException):
        we.InviteLinkedParent('x@example.com')

  def testInviteLinkedParent_NotAMatch(self):
    """We only allow linkage invites when usernames match."""
    self.SignIn()
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException) as cm:
        we.InviteLinkedParent('x@example.com')
      self.assertEqual('Linked account names must match', cm.exception.message)

  @mock.patch('settings.linkable_domains', {'example.com': ['other.com']})
  def testInviteLinkedParent_BadDomain(self):
    """We only allow linkage invites between whitelisted domains."""
    self.SignIn()
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException) as cm:
        we.InviteLinkedParent('user_111@hacker.com')
      self.assertEqual(
          'Linked account unsupported domain', cm.exception.message)

  @mock.patch('settings.linkable_domains', {'example.com': ['other.com']})
  def testInviteLinkedParent_NoSuchParent(self):
    """Verify that the parent account already exists."""
    self.SignIn()
    with self.work_env as we:
      with self.assertRaises(exceptions.NoSuchUserException):
        we.InviteLinkedParent('user_111@other.com')

  @mock.patch('settings.linkable_domains', {'example.com': ['other.com']})
  def testInviteLinkedParent_Normal(self):
    """A child account can invite a matching parent account to link."""
    self.services.user.TestAddUser('user_111@other.com', 555)
    self.SignIn()
    with self.work_env as we:
      we.InviteLinkedParent('user_111@other.com')
      self.assertEqual(
          [(555, 111)], self.services.user.invite_rows)

  def testAcceptLinkedChild_NoInvite(self):
    """A parent account can only accept an exiting invite."""
    self.SignIn()
    self.services.user.invite_rows = [(111, 222)]
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException):
        we.AcceptLinkedChild(333)

    self.SignIn(user_id=222)
    self.services.user.invite_rows = [(111, 333)]
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException):
        we.AcceptLinkedChild(333)

  def testAcceptLinkedChild_Normal(self):
    """A parent account can accept an invite from a child."""
    self.SignIn()
    self.services.user.invite_rows = [(111, 222)]
    with self.work_env as we:
      we.AcceptLinkedChild(222)
      self.assertEqual(
        [(111, 222)], self.services.user.linked_account_rows)
      self.assertEqual(
        [], self.services.user.invite_rows)

  def testUnlinkAccounts_NotAllowed(self):
    """Reject attempts to unlink someone else's accounts."""
    self.SignIn(user_id=333)
    with self.work_env as we:
      with self.assertRaises(permissions.PermissionException):
        we.UnlinkAccounts(111, 222)

  def testUnlinkAccounts_AdminIsAllowed(self):
    """Site admins may unlink someone else's accounts."""
    self.SignIn(user_id=444)
    self.services.user.linked_account_rows = [(111, 222)]
    with self.work_env as we:
      we.UnlinkAccounts(111, 222)
    self.assertNotIn((111, 222), self.services.user.linked_account_rows)

  def testUnlinkAccounts_Normal(self):
    """A parent or child can unlink their linked account."""
    self.SignIn(user_id=111)
    self.services.user.linked_account_rows = [(111, 222), (333, 444)]
    with self.work_env as we:
      we.UnlinkAccounts(111, 222)
    self.assertEqual([(333, 444)], self.services.user.linked_account_rows)

    self.SignIn(user_id=222)
    self.services.user.linked_account_rows = [(111, 222), (333, 444)]
    with self.work_env as we:
      we.UnlinkAccounts(111, 222)
    self.assertEqual([(333, 444)], self.services.user.linked_account_rows)

  def testUpdateUserSettings(self):
    """We can update the settings of the logged in user."""
    self.SignIn()
    user = self.services.user.GetUser(self.cnxn, 111)
    with self.work_env as we:
      we.UpdateUserSettings(
          user,
          obscure_email=True,
          dismissed_cues=['code_of_conduct'],
          keep_people_perms_open=True)

    self.assertTrue(user.obscure_email)
    self.assertTrue(user.keep_people_perms_open)
    self.assertEqual(['code_of_conduct'], user.dismissed_cues)

  def testUpdateUserSettings_Anon(self):
    """A user must be logged in."""
    anon = self.services.user.GetUser(self.cnxn, 0)
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException):
        we.UpdateUserSettings(anon, keep_people_perms_open=True)

  def testGetUserPrefs_Anon(self):
    """Anon always has empty prefs."""
    with self.work_env as we:
      userprefs = we.GetUserPrefs(0)

    self.assertEqual(0, userprefs.user_id)
    self.assertEqual([], userprefs.prefs)

  def testGetUserPrefs_Mine_Empty(self):
    """User who never set any pref gets empty prefs."""
    self.SignIn()
    with self.work_env as we:
      userprefs = we.GetUserPrefs(111)

    self.assertEqual(111, userprefs.user_id)
    self.assertEqual([], userprefs.prefs)

  def testGetUserPrefs_Mine_Some(self):
    """User who set a pref gets it back."""
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='code_font', value='true')])
    self.SignIn()
    with self.work_env as we:
      userprefs = we.GetUserPrefs(111)

    self.assertEqual(111, userprefs.user_id)
    self.assertEqual(1, len(userprefs.prefs))
    self.assertEqual('code_font', userprefs.prefs[0].name)
    self.assertEqual('true', userprefs.prefs[0].value)

  def testGetUserPrefs_Other_Allowed(self):
    """A site admin can read another user's prefs."""
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='code_font', value='true')])
    self.SignIn(user_id=self.admin_user.user_id)

    with self.work_env as we:
      userprefs = we.GetUserPrefs(111)

    self.assertEqual(111, userprefs.user_id)
    self.assertEqual(1, len(userprefs.prefs))
    self.assertEqual('code_font', userprefs.prefs[0].name)
    self.assertEqual('true', userprefs.prefs[0].value)

  def testGetUserPrefs_Other_Denied(self):
    """A non-admin cannot read another user's prefs."""
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='code_font', value='true')])
    # user2 is not a site admin.
    self.SignIn(222)

    with self.work_env as we:
      with self.assertRaises(permissions.PermissionException):
        we.GetUserPrefs(111)

  def _SetUpCorpUsers(self, user_ids):
    self.services.user.TestAddUser('corp_group@example.com', 888)
    self.services.usergroup.TestAddGroupSettings(
        888, 'corp_group@example.com')
    self.services.usergroup.TestAddMembers(888, user_ids)

  # TODO(jrobbins): Update this with user group prefs when implemented.
  @mock.patch('settings.corp_mode_user_groups', ['corp_group@example.com'])
  def testGetUserPrefs_Mine_Corp(self):
    """User who belongs to corp-mode user group gets those prefs."""
    self._SetUpCorpUsers([111, 222])
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='code_font', value='true')])
    self.SignIn()
    with self.work_env as we:
      userprefs = we.GetUserPrefs(111)

    self.assertEqual(111, userprefs.user_id)
    self.assertEqual(3, len(userprefs.prefs))
    self.assertEqual('code_font', userprefs.prefs[0].name)
    self.assertEqual('true', userprefs.prefs[0].value)
    self.assertEqual('restrict_new_issues', userprefs.prefs[1].name)
    self.assertEqual('true', userprefs.prefs[1].value)
    self.assertEqual('public_issue_notice', userprefs.prefs[2].name)
    self.assertEqual('true', userprefs.prefs[2].value)

  @mock.patch('settings.corp_mode_user_groups', ['corp_group@example.com'])
  def testGetUserPrefs_Mine_OptedOut(self):
    """If a corp user has opted out, use that pref value."""
    self._SetUpCorpUsers([111, 222])
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='restrict_new_issues', value='false')])
    self.SignIn()
    with self.work_env as we:
      userprefs = we.GetUserPrefs(111)

    self.assertEqual(111, userprefs.user_id)
    self.assertEqual(2, len(userprefs.prefs))
    self.assertEqual('restrict_new_issues', userprefs.prefs[0].name)
    self.assertEqual('false', userprefs.prefs[0].value)
    self.assertEqual('public_issue_notice', userprefs.prefs[1].name)
    self.assertEqual('true', userprefs.prefs[1].value)

  def testSetUserPrefs_Anon(self):
    """Anon cannot set prefs."""
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException):
        we.SetUserPrefs(0, [])

  def testSetUserPrefs_Mine_Empty(self):
    """Setting zero prefs is a no-op.."""
    self.SignIn(111)

    with self.work_env as we:
      we.SetUserPrefs(111, [])

    prefs_after = self.services.user.GetUserPrefs(self.cnxn, 111)
    self.assertEqual(0, len(prefs_after.prefs))

  def testSetUserPrefs_Mine_Add(self):
    """User can set a preference for the first time."""
    self.SignIn(111)

    with self.work_env as we:
      we.SetUserPrefs(
          111,
          [user_pb2.UserPrefValue(name='code_font', value='true')])

    prefs_after = self.services.user.GetUserPrefs(self.cnxn, 111)
    self.assertEqual(1, len(prefs_after.prefs))
    self.assertEqual('code_font', prefs_after.prefs[0].name)
    self.assertEqual('true', prefs_after.prefs[0].value)

  def testSetUserPrefs_Mine_Overwrite(self):
    """User can change the value of a pref."""
    self.SignIn(111)
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='code_font', value='true')])

    with self.work_env as we:
      we.SetUserPrefs(
          111,
          [user_pb2.UserPrefValue(name='code_font', value='false')])

    prefs_after = self.services.user.GetUserPrefs(self.cnxn, 111)
    self.assertEqual(1, len(prefs_after.prefs))
    self.assertEqual('code_font', prefs_after.prefs[0].name)
    self.assertEqual('false', prefs_after.prefs[0].value)

  def testSetUserPrefs_Mine_Bad(self):
    """User cannot set a preference value that is not valid."""
    self.SignIn(111)

    with self.work_env as we:
      with self.assertRaises(exceptions.InputException):
        we.SetUserPrefs(
            111,
            [user_pb2.UserPrefValue(name='code_font', value='sorta')])
      with self.assertRaises(exceptions.InputException):
        we.SetUserPrefs(
            111,
            [user_pb2.UserPrefValue(name='sign', value='gemini')])

    # Regardless of exceptions, nothing was actually stored.
    prefs_after = self.services.user.GetUserPrefs(self.cnxn, 111)
    self.assertEqual(0, len(prefs_after.prefs))

  def testSetUserPrefs_Other_Allowed(self):
    """A site admin can update another user's prefs."""
    self.SignIn(user_id=self.admin_user.user_id)
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='code_font', value='true')])

    with self.work_env as we:
      we.SetUserPrefs(
          111,
          [user_pb2.UserPrefValue(name='code_font', value='false')])

    prefs_after = self.services.user.GetUserPrefs(self.cnxn, 111)
    self.assertEqual(1, len(prefs_after.prefs))
    self.assertEqual('code_font', prefs_after.prefs[0].name)
    self.assertEqual('false', prefs_after.prefs[0].value)

  def testSetUserPrefs_Other_Denied(self):
    """A non-admin cannot set another user's prefs."""
    # user2 is not a site admin.
    self.SignIn(222)
    self.services.user.SetUserPrefs(
        self.cnxn, 111,
        [user_pb2.UserPrefValue(name='code_font', value='true')])

    with self.work_env as we:
      with self.assertRaises(permissions.PermissionException):
        we.SetUserPrefs(
            111,
            [user_pb2.UserPrefValue(name='code_font', value='false')])

    # Regardless of any exception, the preferences remain unchanged.
    prefs_after = self.services.user.GetUserPrefs(self.cnxn, 111)
    self.assertEqual(1, len(prefs_after.prefs))
    self.assertEqual('code_font', prefs_after.prefs[0].name)
    self.assertEqual('true', prefs_after.prefs[0].value)

  # FUTURE: GetUser()
  # FUTURE: UpdateUser()
  # FUTURE: DeleteUser()
  # FUTURE: ListStarredUsers()

  @mock.patch(
      'features.send_notifications.'
      'PrepareAndSendDeletedFilterRulesNotification')
  def testExpungeUsers(self, fake_pasdfrn):
    """Test user data correctly expunged."""
    # Replace template service mock with fake testing TemplateService
    self.services.template = fake.TemplateService()

    wipeout_emails = ['cow@test.com', 'chicken@test.com', 'llama@test.com',
                      'alpaca@test.com']
    user_1 = self.services.user.TestAddUser('cow@test.com', 111)
    user_2 = self.services.user.TestAddUser('chicken@test.com', 222)
    user_3 = self.services.user.TestAddUser('llama@test.com', 333)
    user_4 = self.services.user.TestAddUser('random@test.com', 888)
    ids_by_email = {user_1.email: user_1.user_id, user_2.email: user_2.user_id,
                    user_3.email: user_3.user_id}
    user_ids = list(ids_by_email.values())

    # set up testing data
    starred_project_id = 19
    self.services.project_star._SetStar(self.mr.cnxn, 12, user_1.user_id, True)
    self.services.user_star.SetStar(
        self.mr.cnxn, user_2.user_id, user_4.user_id, True)
    template = self.services.template.TestAddIssueTemplateDef(
        13, 16, 'template name', owner_id=user_3.user_id)

    self.services.features.TestAddFilterRule(
        16, 'owner:cow@test.com', add_cc_ids=[user_4.user_id])
    self.services.features.TestAddFilterRule(
        16, 'owner:random@test.com',
        add_cc_ids=[user_2.user_id, user_3.user_id])
    self.services.features.TestAddFilterRule(
        17, 'label:random-label', add_notify=[user_3.email])
    kept_rule = self.services.features.TestAddFilterRule(
        16, 'owner:random@test.com', add_notify=['random2@test.com'])

    self.mr.cnxn = mock.Mock()
    self.services.usergroup.group_dag = mock.Mock()

    # call ExpungeUsers
    with self.work_env as we:
      we.ExpungeUsers(wipeout_emails)

    # Assert users expunged in stars
    self.assertFalse(self.services.project_star.IsItemStarredBy(
        self.mr.cnxn, starred_project_id, user_1.user_id))
    self.assertFalse(self.services.user_star.CountItemStars(
        self.mr.cnxn, user_2.user_id))

    # Assert users expunged in quick edits and saved queries
    self.assertItemsEqual(
        self.services.features.expunged_users_in_quick_edits, user_ids)
    self.assertItemsEqual(
        self.services.features.expunged_users_in_saved_queries, user_ids)

    # Assert users expunged in templates and configs
    self.assertIsNone(template.owner_id)
    self.assertItemsEqual(
        self.services.config.expunged_users_in_configs, user_ids)

    # Assert users expunged in issues
    self.assertItemsEqual(
        self.services.issue.expunged_users_in_issues, user_ids)
    self.assertTrue(self.services.issue.enqueue_issues_called)

    # Assert users expunged in spam
    self.assertItemsEqual(
        self.services.spam.expunged_users_in_spam, user_ids)

    # Assert users expunged in hotlists
    self.assertItemsEqual(
        self.services.features.expunged_users_in_hotlists, user_ids)

    # Assert users expunged in groups
    self.assertItemsEqual(
        self.services.usergroup.expunged_users_in_groups, user_ids)

    # Assert filter rules expunged
    self.assertEqual(
        self.services.features.test_rules[16], [kept_rule])
    self.assertEqual(
        self.services.features.test_rules[17], [])

    # Assert mocks
    self.assertEqual(7, len(self.mr.cnxn.Commit.call_args_list))
    self.services.usergroup.group_dag.MarkObsolete.assert_called_once()

    fake_pasdfrn.assert_has_calls(
        [mock.call(
            16,
            'testing-app.appspot.com',
            ['if owner:%s then add cc(s): random@test.com' % (
                framework_constants.DELETED_USER_NAME),
             'if owner:random@test.com then add cc(s): %s, %s' % (
                 framework_constants.DELETED_USER_NAME,
                 framework_constants.DELETED_USER_NAME)]),
         mock.call(
             17,
             'testing-app.appspot.com',
             ['if label:random-label then notify: %s' % (
                 framework_constants.DELETED_USER_NAME)])
        ])


  # FUTURE: CreateGroup()
  # FUTURE: ListGroups()
  # FUTURE: UpdateGroup()
  # FUTURE: DeleteGroup()

  def AddIssueToHotlist(self, hotlist_id, issue_id=78901, adder_id=111):
    self.services.features.AddIssuesToHotlists(
        self.cnxn, [hotlist_id], [(issue_id, adder_id, 0, '')],
        None, None, None)

  def testCreateHotlist_Normal(self):
    """We can create a hotlist."""
    issue_1 = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue_1)

    self.SignIn()
    with self.work_env as we:
      hotlist = we.CreateHotlist(
          'name', 'summary', 'description', [222], [78901], False)

    self.assertEqual('name', hotlist.name)
    self.assertEqual('summary', hotlist.summary)
    self.assertEqual('description', hotlist.description)
    self.assertEqual([111], hotlist.owner_ids)
    self.assertEqual([222], hotlist.editor_ids)
    self.assertEqual([78901], [item.issue_id for item in hotlist.items])
    self.assertEqual(False, hotlist.is_private)

  def testCreateHotlist_AnonCantCreateHotlist(self):
    """We must be signed in to create a hotlist."""
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.CreateHotlist('name', 'summary', 'description', [], [222], False)

  def testCreateHotlist_InvalidName(self):
    """We can't create a hotlist with an invalid name."""
    self.SignIn()
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.CreateHotlist(
            '***Invalid***', 'summary', 'description', [], [], False)

  def testCreateHotlist_HotlistAlreadyExists(self):
    """We can't create a hotlist with a name that already exists."""
    self.SignIn()
    with self.work_env as we:
      we.CreateHotlist('name', 'summary', 'description', [], [], False)

    with self.assertRaises(features_svc.HotlistAlreadyExists):
      with self.work_env as we:
        we.CreateHotlist('name', 'foo', 'bar', [], [], True)

  def testGetHotlist_Normal(self):
    """We can get an existing hotlist by hotlist_id."""
    hotlist = self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[])

    with self.work_env as we:
      actual = we.GetHotlist(hotlist.hotlist_id)

    self.assertEqual(hotlist, actual)

  def testGetHotlist_NoneHotlist(self):
    """We reject attempts to pass a None hotlist_id."""
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        _actual = we.GetHotlist(None)

  def testGetHotlist_NoSuchHotlist(self):
    """We reject attempts to get a non-existent hotlist."""
    with self.assertRaises(features_svc.NoSuchHotlistException):
      with self.work_env as we:
        _actual = we.GetHotlist(999)

  def testListHotlistsByUser_Normal(self):
    self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[])

    self.SignIn()
    with self.work_env as we:
      hotlists = we.ListHotlistsByUser(111)

    self.assertEqual(1, len(hotlists))
    hotlist = hotlists[0]
    self.assertEqual([111], hotlist.owner_ids)
    self.assertEqual([], hotlist.editor_ids)
    self.assertEqual('Fake-Hotlist', hotlist.name)
    self.assertEqual('Summary', hotlist.summary)
    self.assertEqual('Description', hotlist.description)

  def testListHotlistsByUser_AnotherUser(self):
    self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[333], editor_ids=[])

    self.SignIn()
    with self.work_env as we:
      hotlists = we.ListHotlistsByUser(333)

    self.assertEqual(1, len(hotlists))
    hotlist = hotlists[0]
    self.assertEqual([333], hotlist.owner_ids)
    self.assertEqual([], hotlist.editor_ids)
    self.assertEqual('Fake-Hotlist', hotlist.name)
    self.assertEqual('Summary', hotlist.summary)
    self.assertEqual('Description', hotlist.description)

  def testListHotlistsByUser_NotSignedIn(self):
    self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[])

    with self.work_env as we:
      hotlists = we.ListHotlistsByUser(111)

    self.assertEqual(1, len(hotlists))
    hotlist = hotlists[0]
    self.assertEqual([111], hotlist.owner_ids)
    self.assertEqual([], hotlist.editor_ids)
    self.assertEqual('Fake-Hotlist', hotlist.name)
    self.assertEqual('Summary', hotlist.summary)
    self.assertEqual('Description', hotlist.description)

  def testListHotlistsByUser_NoUserId(self):
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.ListHotlistsByUser(None)


  def testListHotlistsByUser_Empty(self):
    self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[333], editor_ids=[])

    self.SignIn()
    with self.work_env as we:
      hotlists = we.ListHotlistsByUser(111)

    self.assertEqual(0, len(hotlists))

  def testListHotlistsByUser_NoHotlists(self):
    self.SignIn()
    with self.work_env as we:
      hotlists = we.ListHotlistsByUser(111)

    self.assertEqual(0, len(hotlists))

  def testListHotlistsByUser_PrivateHotlistAsOwner(self):
    self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[333], is_private=True)

    self.SignIn()
    with self.work_env as we:
      hotlists = we.ListHotlistsByUser(333)

    self.assertEqual(1, len(hotlists))
    hotlist = hotlists[0]
    self.assertEqual([111], hotlist.owner_ids)
    self.assertEqual([333], hotlist.editor_ids)
    self.assertEqual('Fake-Hotlist', hotlist.name)
    self.assertEqual('Summary', hotlist.summary)
    self.assertEqual('Description', hotlist.description)

  def testListHotlistsByUser_PrivateHotlistAsEditor(self):
    self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[333], editor_ids=[111], is_private=True)

    self.SignIn()
    with self.work_env as we:
      hotlists = we.ListHotlistsByUser(333)

    self.assertEqual(1, len(hotlists))
    hotlist = hotlists[0]
    self.assertEqual([333], hotlist.owner_ids)
    self.assertEqual([111], hotlist.editor_ids)
    self.assertEqual('Fake-Hotlist', hotlist.name)
    self.assertEqual('Summary', hotlist.summary)
    self.assertEqual('Description', hotlist.description)

  def testListHotlistsByUser_PrivateHotlistNoAcess(self):
    self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[333], editor_ids=[], is_private=True)

    self.SignIn()
    with self.work_env as we:
      hotlists = we.ListHotlistsByUser(333)

    self.assertEqual(0, len(hotlists))

  def testListHotlistsByIssue_Normal(self):
    issue = fake.MakeTestIssue(789, 1, 'sum1', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    hotlist = self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[])
    self.AddIssueToHotlist(hotlist.hotlist_id)

    self.SignIn()
    with self.work_env as we:
      hotlists = we.ListHotlistsByIssue(78901)

    self.assertEqual(1, len(hotlists))
    hotlist = hotlists[0]
    self.assertEqual([111], hotlist.owner_ids)
    self.assertEqual([], hotlist.editor_ids)
    self.assertEqual('Fake-Hotlist', hotlist.name)
    self.assertEqual('Summary', hotlist.summary)
    self.assertEqual('Description', hotlist.description)

  def testListHotlistsByIssue_NotSignedIn(self):
    issue = fake.MakeTestIssue(789, 1, 'sum1', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    hotlist = self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[])
    self.AddIssueToHotlist(hotlist.hotlist_id)

    with self.work_env as we:
      hotlists = we.ListHotlistsByIssue(78901)

    self.assertEqual(1, len(hotlists))
    hotlist = hotlists[0]
    self.assertEqual([111], hotlist.owner_ids)
    self.assertEqual([], hotlist.editor_ids)
    self.assertEqual('Fake-Hotlist', hotlist.name)
    self.assertEqual('Summary', hotlist.summary)
    self.assertEqual('Description', hotlist.description)

  def testListHotlistsByIssue_NotAllowedToSeeIssue(self):
    issue = fake.MakeTestIssue(789, 1, 'sum1', 'New', 111, issue_id=78901)
    issue.labels = ['Restrict-View-CoreTeam']
    self.services.issue.TestAddIssue(issue)
    hotlist = self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[])
    self.AddIssueToHotlist(hotlist.hotlist_id)

    # We should get a permission exception
    self.SignIn(333)
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.ListHotlistsByIssue(78901)

  def testListHotlistsByIssue_NoSuchIssue(self):
    self.SignIn()
    with self.assertRaises(exceptions.NoSuchIssueException):
      with self.work_env as we:
        we.ListHotlistsByIssue(78901)

  def testListHotlistsByIssue_NoHotlists(self):
    issue = fake.MakeTestIssue(789, 1, 'sum1', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)

    self.SignIn()
    with self.work_env as we:
      hotlists = we.ListHotlistsByIssue(78901)

    self.assertEqual(0, len(hotlists))

  def testListHotlistsByIssue_PrivateHotlistAsOwner(self):
    issue = fake.MakeTestIssue(789, 1, 'sum1', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    hotlist = self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[333], is_private=True)
    self.AddIssueToHotlist(hotlist.hotlist_id)

    self.SignIn()
    with self.work_env as we:
      hotlists = we.ListHotlistsByIssue(78901)

    self.assertEqual(1, len(hotlists))
    hotlist = hotlists[0]
    self.assertEqual([111], hotlist.owner_ids)
    self.assertEqual([333], hotlist.editor_ids)
    self.assertEqual('Fake-Hotlist', hotlist.name)
    self.assertEqual('Summary', hotlist.summary)
    self.assertEqual('Description', hotlist.description)

  def testListHotlistsByIssue_PrivateHotlistAsEditor(self):
    issue = fake.MakeTestIssue(789, 1, 'sum1', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    hotlist = self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[333], editor_ids=[111], is_private=True)
    self.AddIssueToHotlist(hotlist.hotlist_id)

    self.SignIn()
    with self.work_env as we:
      hotlists = we.ListHotlistsByIssue(78901)

    self.assertEqual(1, len(hotlists))
    hotlist = hotlists[0]
    self.assertEqual([333], hotlist.owner_ids)
    self.assertEqual([111], hotlist.editor_ids)
    self.assertEqual('Fake-Hotlist', hotlist.name)
    self.assertEqual('Summary', hotlist.summary)
    self.assertEqual('Description', hotlist.description)

  def testListHotlistsByIssue_PrivateHotlistNoAcess(self):
    issue = fake.MakeTestIssue(789, 1, 'sum1', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    hotlist = self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[444], editor_ids=[333], is_private=True)
    self.AddIssueToHotlist(hotlist.hotlist_id)

    self.SignIn()
    with self.work_env as we:
      hotlists = we.ListHotlistsByIssue(78901)

    self.assertEqual(0, len(hotlists))

  def testListRecentlyVisitedHotlists(self):
    hotlists = [
        self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
            owner_ids=[444], editor_ids=[111]),
        self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist-2', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[333]),
        self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Private-Hotlist', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[333], is_private=True),
        self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Private-Hotlist-2', 'Summary', 'Description',
            owner_ids=[222], editor_ids=[333], is_private=True)]

    for hotlist in hotlists:
      self.work_env.services.user.AddVisitedHotlist(
          self.cnxn, 111, hotlist.hotlist_id)

    self.SignIn()
    with self.work_env as we:
      visited_hotlists = we.ListRecentlyVisitedHotlists()

    # We don't have permission to see the last hotlist, because it is marked as
    # private and we're not owners or editors of it.
    self.assertEqual(hotlists[:-1], visited_hotlists)

  def testListRecentlyVisitedHotlists_Anon(self):
    with self.work_env as we:
      self.assertEqual([], we.ListRecentlyVisitedHotlists())

  def testListStarredHotlists(self):
    hotlists = [
        self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
            owner_ids=[444], editor_ids=[111]),
        self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist-2', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[333]),
        self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Private-Hotlist', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[333], is_private=True),
        self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Private-Hotlist-2', 'Summary', 'Description',
            owner_ids=[222], editor_ids=[333], is_private=True)]

    for hotlist in hotlists:
      self.work_env.services.hotlist_star.SetStar(
          self.cnxn, hotlist.hotlist_id, 111, True)

    self.SignIn()
    with self.work_env as we:
      visited_hotlists = we.ListStarredHotlists()

    # We don't have permission to see the last hotlist, because it is marked as
    # private and we're not owners or editors of it.
    self.assertEqual(hotlists[:-1], visited_hotlists)

  def testListStarredHotlists_Anon(self):
    with self.work_env as we:
      self.assertEqual([], we.ListStarredHotlists())

  def testStarHotlist_Normal(self):
    """We can star and unstar a hotlist."""
    hotlist_id = self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[]).hotlist_id

    self.SignIn()
    with self.work_env as we:
      self.assertFalse(we.IsHotlistStarred(hotlist_id))
      we.StarHotlist(hotlist_id, True)
      self.assertTrue(we.IsHotlistStarred(hotlist_id))
      we.StarHotlist(hotlist_id, False)
      self.assertFalse(we.IsHotlistStarred(hotlist_id))

  def testStarHotlist_NoHotlistSpecified(self):
    """A hotlist must be specified."""
    self.SignIn()
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.StarHotlist(None, True)

  def testStarHotlist_NoSuchHotlist(self):
    """We can't star a nonexistent hotlist."""
    self.SignIn()
    with self.assertRaises(features_svc.NoSuchHotlistException):
      with self.work_env as we:
        we.StarHotlist(999, True)

  def testStarHotlist_Anon(self):
    """Anon user can't star a hotlist."""
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.StarHotlist(999, True)

  # testIsHotlistStarred_Normal is Tested by method testStarHotlist_Normal().

  def testIsHotlistStarred_Anon(self):
    """Anon user can't star a hotlist."""
    with self.work_env as we:
      self.assertFalse(we.IsHotlistStarred(999))

  def testIsHotlistStarred_NoHotlistSpecified(self):
    """A Hotlist ID must be specified."""
    with self.work_env as we:
      with self.assertRaises(exceptions.InputException):
        we.IsHotlistStarred(None)

  def testIsHotlistStarred_NoSuchHotlist(self):
    """We can't check for stars on a nonexistent hotlist."""
    self.SignIn()
    with self.assertRaises(features_svc.NoSuchHotlistException):
      with self.work_env as we:
        we.IsHotlistStarred(999)

  def testGetHotlistStarCount(self):
    hotlist = self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[])
    self.services.hotlist_star.SetStar(
        self.cnxn, hotlist.hotlist_id, 111, True)
    self.services.hotlist_star.SetStar(
        self.cnxn, hotlist.hotlist_id, 222, True)

    with self.work_env as we:
      self.assertEqual(2, we.GetHotlistStarCount(hotlist.hotlist_id))

  def testGetHotlistStarCount_NoneHotlist(self):
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.GetHotlistStarCount(None)

  def testGetHotlistStarCount_NoSuchHotlist(self):
    with self.assertRaises(features_svc.NoSuchHotlistException):
      with self.work_env as we:
        we.GetHotlistStarCount(123)

  def testCheckHotlistName_OK(self):
    self.SignIn()
    with self.work_env as we:
      error = we.CheckHotlistName('Fake-Hotlist')
    self.assertIsNone(error)

  def testCheckHotlistName_Anon(self):
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.CheckHotlistName('Fake-Hotlist')

  def testCheckHotlistName_InvalidName(self):
    self.SignIn()
    with self.work_env as we:
      error = we.CheckHotlistName('**Invalid**')
    self.assertIsNotNone(error)

  def testCheckHotlistName_AlreadyExists(self):
    self.work_env.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[])

    self.SignIn()
    with self.work_env as we:
      error = we.CheckHotlistName('Fake-Hotlist')
    self.assertIsNotNone(error)

  def testRemoveIssuesFromHotlists(self):
    """We can remove issues from hotlists."""
    issue1 = fake.MakeTestIssue(789, 1, 'sum1', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue1)
    issue2 = fake.MakeTestIssue(789, 2, 'sum2', 'New', 111, issue_id=78902)
    self.services.issue.TestAddIssue(issue2)

    hotlist1 = self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[])
    self.AddIssueToHotlist(hotlist1.hotlist_id, issue1.issue_id)
    self.AddIssueToHotlist(hotlist1.hotlist_id, issue2.issue_id)

    hotlist2 = self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist-2', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[])
    self.AddIssueToHotlist(hotlist2.hotlist_id, issue1.issue_id)

    self.SignIn()
    with self.work_env as we:
      we.RemoveIssuesFromHotlists(
          [hotlist1.hotlist_id, hotlist2.hotlist_id], [issue1.issue_id])

    self.assertEqual(
        [issue2.issue_id], [item.issue_id for item in hotlist1.items])
    self.assertEqual(0, len(hotlist2.items))

  def testRemoveIssuesFromHotlists_RemoveIssueNotInHotlist(self):
    """Removing an issue from a hotlist that doesn't have it has no effect."""
    issue1 = fake.MakeTestIssue(789, 1, 'sum1', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue1)
    issue2 = fake.MakeTestIssue(789, 2, 'sum2', 'New', 111, issue_id=78902)
    self.services.issue.TestAddIssue(issue2)

    hotlist1 = self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[])
    self.AddIssueToHotlist(hotlist1.hotlist_id, issue1.issue_id)
    self.AddIssueToHotlist(hotlist1.hotlist_id, issue2.issue_id)

    hotlist2 = self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist-2', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[])
    self.AddIssueToHotlist(hotlist2.hotlist_id, issue1.issue_id)

    self.SignIn()
    with self.work_env as we:
      # Issue 2 is not in Fake-Hotlist-2
      we.RemoveIssuesFromHotlists([hotlist2.hotlist_id], [issue2.issue_id])

    self.assertEqual(
        [issue1.issue_id, issue2.issue_id],
        [item.issue_id for item in hotlist1.items])
    self.assertEqual(
        [issue1.issue_id],
        [item.issue_id for item in hotlist2.items])

  def testRemoveIssuesFromHotlists_NotAllowed(self):
    """Only owners and editors can remove issues."""
    hotlist = self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[])

    # 333 is not an owner or editor.
    self.SignIn(333)
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.RemoveIssuesFromHotlists([hotlist.hotlist_id], [1234])

  def testRemoveIssuesFromHotlists_NoSuchHotlist(self):
    """We can't remove issues from non existent hotlists."""
    with self.assertRaises(features_svc.NoSuchHotlistException):
      with self.work_env as we:
        we.RemoveIssuesFromHotlists([1, 2, 3], [4, 5, 6])

  def testAddIssuesToHotlists(self):
    """We can add issues to hotlists."""
    issue1 = fake.MakeTestIssue(789, 1, 'sum1', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue1)
    issue2 = fake.MakeTestIssue(789, 2, 'sum2', 'New', 111, issue_id=78902)
    self.services.issue.TestAddIssue(issue2)

    hotlist1 = self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[])
    hotlist2 = self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist-2', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[])

    self.SignIn()
    with self.work_env as we:
      we.AddIssuesToHotlists(
          [hotlist1.hotlist_id, hotlist2.hotlist_id],
          [issue1.issue_id, issue2.issue_id],
          'Foo')

    self.assertEqual(
        [issue1.issue_id, issue2.issue_id],
        [item.issue_id for item in hotlist1.items])
    self.assertEqual(
        [issue1.issue_id, issue2.issue_id],
        [item.issue_id for item in hotlist2.items])

    self.assertEqual(['Foo', 'Foo'], [item.note for item in hotlist1.items])
    self.assertEqual(['Foo', 'Foo'], [item.note for item in hotlist2.items])

  def testAddIssuesToHotlists_IssuesAlreadyInHotlist(self):
    """Adding an issue to a hotlist that already has it has no effect."""
    issue1 = fake.MakeTestIssue(789, 1, 'sum1', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue1)
    issue2 = fake.MakeTestIssue(789, 2, 'sum2', 'New', 111, issue_id=78902)
    self.services.issue.TestAddIssue(issue2)

    hotlist1 = self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[])
    self.AddIssueToHotlist(hotlist1.hotlist_id, issue1.issue_id)
    self.AddIssueToHotlist(hotlist1.hotlist_id, issue2.issue_id)

    hotlist2 = self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist-2', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[])
    self.AddIssueToHotlist(hotlist2.hotlist_id, issue1.issue_id)

    self.SignIn()
    with self.work_env as we:
      # Issue 1 is in both hotlists
      we.AddIssuesToHotlists(
          [hotlist1.hotlist_id, hotlist2.hotlist_id], [issue1.issue_id], None)

    self.assertEqual(
        [issue1.issue_id, issue2.issue_id],
        [item.issue_id for item in hotlist1.items])
    self.assertEqual(
        [issue1.issue_id],
        [item.issue_id for item in hotlist2.items])

  def testAddIssuesToHotlists_NotViewable(self):
    """Users can add viewable issues to hotlists."""
    issue1 = fake.MakeTestIssue(
        789, 1, 'sum1', 'New', 111, issue_id=78901)
    issue1.labels = ['Restrict-View-CoreTeam']
    self.services.issue.TestAddIssue(issue1)
    hotlist = self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
            owner_ids=[333], editor_ids=[])

    self.SignIn(user_id=333)
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.AddIssuesToHotlists([hotlist.hotlist_id], [78901], None)

  def testAddIssuesToHotlists_NotAllowed(self):
    """Only owners and editors can add issues."""
    hotlist = self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[])

    # 333 is not an owner or editor.
    self.SignIn(user_id=333)
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.AddIssuesToHotlists([hotlist.hotlist_id], [1234], None)

  def testAddIssuesToHotlists_NoSuchHotlist(self):
    """We can't remove issues from non existent hotlists."""
    with self.assertRaises(features_svc.NoSuchHotlistException):
      with self.work_env as we:
        we.AddIssuesToHotlists([1, 2, 3], [4, 5, 6], None)

  def testUpdateHotlistIssueNote(self):
    issue = fake.MakeTestIssue(789, 1, 'sum1', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)

    hotlist = self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[])
    self.AddIssueToHotlist(hotlist.hotlist_id, issue.issue_id)

    self.SignIn()
    with self.work_env as we:
      we.UpdateHotlistIssueNote(hotlist.hotlist_id, 78901, 'Note')

    self.assertEqual('Note', hotlist.items[0].note)

  def testUpdateHotlistIssueNote_IssueNotInHotlist(self):
    issue = fake.MakeTestIssue(789, 1, 'sum1', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)

    hotlist = self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[])

    self.SignIn()
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.UpdateHotlistIssueNote(hotlist.hotlist_id, 78901, 'Note')

  def testUpdateHotlistIssueNote_NoSuchIssue(self):
    hotlist = self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[])

    self.SignIn()
    with self.assertRaises(exceptions.NoSuchIssueException):
      with self.work_env as we:
        we.UpdateHotlistIssueNote(hotlist.hotlist_id, 78901, 'Note')

  def testUpdateHotlistIssueNote_CantEditHotlist(self):
    hotlist = self.work_env.services.features.CreateHotlist(
            self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
            owner_ids=[111], editor_ids=[])

    self.SignIn(user_id=333)
    with self.assertRaises(permissions.PermissionException):
      with self.work_env as we:
        we.UpdateHotlistIssueNote(hotlist.hotlist_id, 78901, 'Note')

  def testUpdateHotlistIssueNote_NoSuchHotlist(self):
    self.SignIn()
    with self.assertRaises(features_svc.NoSuchHotlistException):
      with self.work_env as we:
        we.UpdateHotlistIssueNote(1234, 78901, 'Note')

  # FUTURE: UpdateHotlist()
  # FUTURE: DeleteHotlist()

  def testDismissCue(self):
    user = self.services.user.test_users[111]
    self.assertEqual(0, len(user.dismissed_cues))

    self.SignIn()
    with self.work_env as we:
      we.DismissCue('code_of_conduct')

    self.assertEqual(['code_of_conduct'],
                     user.dismissed_cues)

  def testDismissCue_NoCueId(self):
    user = self.services.user.test_users[111]

    self.SignIn()
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.DismissCue(None)

    self.assertEqual([], user.dismissed_cues)

  def testDismissCue_NotSignedIn(self):
    user = self.services.user.test_users[111]

    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.DismissCue(None)

    self.assertEqual([], user.dismissed_cues)

  def testDismissCue_CueAlreadyDismissed(self):
    user = self.services.user.test_users[111]
    user.dismissed_cues = ['code_of_conduct']

    self.SignIn()
    with self.work_env as we:
      we.DismissCue('code_of_conduct')

    self.assertEqual(['code_of_conduct'],
                     user.dismissed_cues)

  def testDismissCue_UnrecognizedCueId(self):
    user = self.services.user.test_users[111]

    self.SignIn()
    with self.assertRaises(exceptions.InputException):
      with self.work_env as we:
        we.DismissCue('foo')

    self.assertEqual([], user.dismissed_cues)

  def setUpExpungeUsersFromStars(self):
    config = fake.MakeTestConfig(789, [], [])
    self.work_env.services.project_star.SetStarsBatch(
        self.cnxn, 789, [222, 444, 555], True)
    self.work_env.services.issue_star.SetStarsBatch(
        self.cnxn, self.services, config, 78901, [222, 444, 666], True)
    self.work_env.services.hotlist_star.SetStarsBatch(
        self.cnxn, 1678, [222, 444, 555], True)
    self.work_env.services.user_star.SetStarsBatch(
        self.cnxn, 888, [222, 333, 777], True)
    self.work_env.services.user_star.SetStarsBatch(
        self.cnxn, 999, [111, 222, 333], True)

  def testExpungeUsersFromStars(self):
    self.setUpExpungeUsersFromStars()
    user_ids = [999, 222, 555]
    self.work_env.expungeUsersFromStars(user_ids)
    self.assertEqual(
        self.work_env.services.project_star.LookupItemStarrers(self.cnxn, 789),
        [444])
    self.assertEqual(
        self.work_env.services.issue_star.LookupItemStarrers(self.cnxn, 78901),
        [444, 666])
    self.assertEqual(
        self.work_env.services.hotlist_star.LookupItemStarrers(self.cnxn, 1678),
        [444])
    self.assertEqual(
        self.work_env.services.user_star.LookupItemStarrers(self.cnxn, 888),
        [333, 777])
    self.assertEqual(
        self.work_env.services.user_star.expunged_item_ids, [999, 222, 555])
