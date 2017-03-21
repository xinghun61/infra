# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the API v1."""

import endpoints
import unittest
import webtest
from google.appengine.api import oauth
from mock import Mock
from protorpc import messages
from protorpc import message_types

from framework import monorailrequest
from framework import permissions
from framework import template_helpers
from proto import project_pb2
from proto import tracker_pb2
from search import frontendsearchpipeline
from services import api_svc_v1
from services import issue_svc
from services import project_svc
from services import service_manager
from services import tracker_fulltext
from services import user_svc
from testing import fake
from testing_utils import testing
from tracker import tracker_bizobj


def MakeFakeServiceManager():
  return service_manager.Services(
      user=fake.UserService(),
      usergroup=fake.UserGroupService(),
      project=fake.ProjectService(),
      config=fake.ConfigService(),
      issue=fake.IssueService(),
      issue_star=fake.IssueStarService(),
      features=fake.FeaturesService(),
      cache_manager=fake.CacheManager())


class FakeMonorailApiRequest(object):

  def __init__(self, request, services, perms=None):
    self.cnxn = None
    self.auth = monorailrequest.AuthData.FromEmail(
        self.cnxn, request['requester'], services)
    self.me_user_id = self.auth.user_id
    self.project_name = None
    self.project = None
    self.viewed_username = None
    self.viewed_user_auth = None
    self.config = None
    if 'userId' in request:
      self.viewed_username = request['userId']
      self.viewed_user_auth = monorailrequest.AuthData.FromEmail(
          self.cnxn, self.viewed_username, services)
    elif 'groupName' in request:
      self.viewed_username = request['groupName']
      try:
        self.viewed_user_auth = monorailrequest.AuthData.FromEmail(
          self.cnxn, self.viewed_username, services)
      except user_svc.NoSuchUserException:
        self.viewed_user_auth = None
    if 'projectId' in request:
      self.project_name = request['projectId']
      self.project = services.project.GetProjectByName(
        self.cnxn, self.project_name)
      self.config = services.config.GetProjectConfig(
          self.cnxn, self.project_id)
    self.perms = perms or permissions.GetPermissions(
        self.auth.user_pb, self.auth.effective_ids, self.project)
    self.granted_perms = set()

    self.params = {
      'can': request.get('can', 1),
      'start': request.get('startIndex', 0),
      'num': request.get('maxResults', 100),
      'q': request.get('q', ''),
      'sort': request.get('sort', ''),
      'groupby': '',
      'projects': request.get('additionalProject', []) + [self.project_name]}
    self.use_cached_searches = True
    self.errors = template_helpers.EZTError()
    self.mode = None

    self.query_project_names = self.GetParam('projects')
    self.group_by_spec = self.GetParam('groupby')
    self.sort_spec = self.GetParam('sort')
    self.query = self.GetParam('q')
    self.can = self.GetParam('can')
    self.start = self.GetParam('start')
    self.num = self.GetParam('num')

  @property
  def project_id(self):
    return self.project.project_id if self.project else None

  def GetParam(self, query_param_name, default_value=None,
               _antitamper_re=None):
    return self.params.get(query_param_name, default_value)

  def GetPositiveIntParam(self, query_param_name, default_value=None):
    """Returns 0 if the user-provided value is less than 0."""
    return max(self.GetParam(query_param_name, default_value=default_value),
               0)


class FakeFrontendSearchPipeline(object):

  def __init__(self):
    issue1 = fake.MakeTestIssue(
        project_id=12345, local_id=1, owner_id=2, status='New', summary='sum')
    issue2 = fake.MakeTestIssue(
        project_id=12345, local_id=2, owner_id=2, status='New', summary='sum')
    self.allowed_results = [issue1, issue2]
    self.visible_results = [issue1]
    self.total_count = len(self.allowed_results)
    self.config = None
    self.projectId = 0

  def SearchForIIDs(self):
    pass

  def MergeAndSortIssues(self):
    pass

  def Paginate(self):
    pass


class MonorailApiTest(testing.EndpointsTestCase):

  api_service_cls = api_svc_v1.MonorailApi

  def setUp(self):
    super(MonorailApiTest, self).setUp()
    self.requester = RequesterMock(email='requester@example.com')
    self.mock(endpoints, 'get_current_user', lambda: self.requester)
    self.config = None
    self.services = MakeFakeServiceManager()
    self.mock(api_svc_v1.MonorailApi, '_services', self.services)
    self.services.user.TestAddUser('requester@example.com', 1)
    self.services.user.TestAddUser('user@example.com', 2)
    self.services.user.TestAddUser('group@example.com', 123)
    self.services.usergroup.TestAddGroupSettings(123, 'group@example.com')
    self.request = {
          'userId': 'user@example.com',
          'ownerProjectsOnly': False,
          'requester': 'requester@example.com',
          'projectId': 'test-project',
          'issueId': 1}
    self.mock(api_svc_v1.MonorailApi, 'mar_factory',
              lambda x, y: FakeMonorailApiRequest(self.request, self.services))

    # api_base_checks is tested in AllBaseChecksTest,
    # so mock it to reduce noise.
    self.mock(api_svc_v1, 'api_base_checks',
              lambda x, y, z, u, v, w: ('id', 'email'))

    self.mock(tracker_fulltext, 'IndexIssues', lambda x, y, z, u, v: None)

  def SetUpComponents(
      self, project_id, component_id, component_name, component_doc='doc',
      deprecated=False, admin_ids=None, cc_ids=None, created=100000, creator=1):
    admin_ids = admin_ids or []
    cc_ids = cc_ids or []
    self.config = self.services.config.GetProjectConfig(
        'fake cnxn', project_id)
    self.services.config.StoreConfig('fake cnxn', self.config)
    cd = tracker_bizobj.MakeComponentDef(
        component_id, project_id, component_name, component_doc, deprecated,
        admin_ids, cc_ids, created, creator)
    self.config.component_defs.append(cd)

  def SetUpFieldDefs(
      self, field_id, project_id, field_name, field_type_int,
      min_value=0, max_value=100, needs_member=False, docstring='doc'):
    self.config = self.services.config.GetProjectConfig(
        'fake cnxn', project_id)
    self.services.config.StoreConfig('fake cnxn', self.config)
    fd = tracker_bizobj.MakeFieldDef(
        field_id, project_id, field_name, field_type_int, '',
        '', False, False, False, min_value, max_value, None, needs_member,
        None, '', tracker_pb2.NotifyTriggers.NEVER, docstring, False)
    self.config.field_defs.append(fd)

  def testUsersGet_NoProject(self):
    """The viewed user has no projects."""

    self.services.project.TestAddProject(
        'public-project', owner_ids=[1])
    resp = self.call_api('users_get', self.request).json_body
    expected = {
        'id': '2',
        'kind': 'monorail#user'}
    self.assertEqual(expected, resp)

  def testUsersGet_PublicProject(self):
    """The viewed user has one public project."""

    self.services.project.TestAddProject(
        'public-project', owner_ids=[2])
    resp = self.call_api('users_get', self.request).json_body

    self.assertEqual(1, len(resp['projects']))
    self.assertEqual('public-project', resp['projects'][0]['name'])

  def testUsersGet_PrivateProject(self):
    """The viewed user has one project but the requester cannot view."""

    self.services.project.TestAddProject(
        'private-project', owner_ids=[2],
        access=project_pb2.ProjectAccess.MEMBERS_ONLY)
    resp = self.call_api('users_get', self.request).json_body
    self.assertNotIn('projects', resp)

  def testUsersGet_OwnerProjectOnly(self):
    """The viewed user has different roles of projects."""

    self.services.project.TestAddProject(
        'owner-project', owner_ids=[2])
    self.services.project.TestAddProject(
        'member-project', owner_ids=[1], committer_ids=[2])
    resp = self.call_api('users_get', self.request).json_body
    self.assertEqual(2, len(resp['projects']))

    self.request['ownerProjectsOnly'] = True
    resp = self.call_api('users_get', self.request).json_body
    self.assertEqual(1, len(resp['projects']))
    self.assertEqual('owner-project', resp['projects'][0]['name'])

  def testIssuesGet_GetIssue(self):
    """Get the requested issue."""

    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')
    self.SetUpFieldDefs(1, 12345, 'Field1', tracker_pb2.FieldTypes.INT_TYPE)

    fv = tracker_pb2.FieldValue(
        field_id=1,
        int_value=11)
    issue1 = fake.MakeTestIssue(
        project_id=12345, local_id=1, owner_id=2, reporter_id=1, status='New',
        summary='sum', component_ids=[1], field_values=[fv])
    self.services.issue.TestAddIssue(issue1)

    resp = self.call_api('issues_get', self.request).json_body
    self.assertEqual(1, resp['id'])
    self.assertEqual('New', resp['status'])
    self.assertEqual('open', resp['state'])
    self.assertFalse(resp['canEdit'])
    self.assertTrue(resp['canComment'])
    self.assertEqual('requester@example.com', resp['author']['name'])
    self.assertEqual('user@example.com', resp['owner']['name'])
    self.assertEqual('API', resp['components'][0])
    self.assertEqual('Field1', resp['fieldValues'][0]['fieldName'])
    self.assertEqual('11', resp['fieldValues'][0]['fieldValue'])

  def testIssuesInsert_BadRequest(self):
    """The request does not specify summary or status."""

    with self.assertRaises(webtest.AppError):
      self.call_api('issues_insert', self.request)

    issue_dict = {
      'status': 'New',
      'summary': 'Test issue',
      'owner': {'name': 'notexist@example.com'}}
    self.request.update(issue_dict)
    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        project_id=12345)
    with self.call_should_fail(400):
      self.call_api('issues_insert', self.request)

    # Invalid field value
    self.SetUpFieldDefs(1, 12345, 'Field1', tracker_pb2.FieldTypes.INT_TYPE)
    issue_dict = {
      'status': 'New',
      'summary': 'Test issue',
      'owner': {'name': 'requester@example.com'},
      'fieldValues': [{'fieldName': 'Field1', 'fieldValue': '111'}]}
    self.request.update(issue_dict)
    with self.call_should_fail(400):
      self.call_api('issues_insert', self.request)

  def testIssuesInsert_NoPermission(self):
    """The requester has no permission to create issues."""

    issue_dict = {
      'status': 'New',
      'summary': 'Test issue'}
    self.request.update(issue_dict)

    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        access=project_pb2.ProjectAccess.MEMBERS_ONLY,
        project_id=12345)
    with self.call_should_fail(403):
      self.call_api('issues_insert', self.request)

  def testIssuesInsert_CreateIssue(self):
    """Create an issue as requested."""

    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        project_id=12345)
    self.SetUpFieldDefs(1, 12345, 'Field1', tracker_pb2.FieldTypes.INT_TYPE)

    issue1 = fake.MakeTestIssue(
        project_id=12345, local_id=1, owner_id=2, reporter_id=1, status='New',
        summary='Test issue')
    self.services.issue.TestAddIssue(issue1)

    issue_dict = {
      'blockedOn': [{'issueId': 1}],
      'cc': [{'name': 'user@example.com'}],
      'description': 'description',
      'labels': ['label1', 'label2'],
      'owner': {'name': 'requester@example.com'},
      'status': 'New',
      'summary': 'Test issue',
      'fieldValues': [{'fieldName': 'Field1', 'fieldValue': '11'}]}
    self.request.update(issue_dict)

    resp = self.call_api('issues_insert', self.request).json_body
    self.assertEqual('New', resp['status'])
    self.assertEqual('requester@example.com', resp['author']['name'])
    self.assertEqual('requester@example.com', resp['owner']['name'])
    self.assertEqual('user@example.com', resp['cc'][0]['name'])
    self.assertEqual(1, resp['blockedOn'][0]['issueId'])
    self.assertEqual([u'label1', u'label2'], resp['labels'])
    self.assertEqual('Test issue', resp['summary'])
    self.assertEqual('Field1', resp['fieldValues'][0]['fieldName'])
    self.assertEqual('11', resp['fieldValues'][0]['fieldValue'])

    new_issue = self.services.issue.GetIssueByLocalID(
        'fake cnxn', 12345, resp['id'])

    starrers = self.services.issue_star.LookupItemStarrers(
        'fake cnxn', new_issue.issue_id)
    self.assertIn(1, starrers)

  def testIssuesList_NoPermission(self):
    """No permission for additional projects."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        project_id=12345)

    self.services.project.TestAddProject(
        'test-project2', owner_ids=[2],
        access=project_pb2.ProjectAccess.MEMBERS_ONLY,
        project_id=123456)
    self.request['additionalProject'] = ['test-project2']
    with self.call_should_fail(403):
      self.call_api('issues_list', self.request)

  def testIssuesList_SearchIssues(self):
    """Find issues of one project."""

    self.mock(frontendsearchpipeline, 'FrontendSearchPipeline',
              lambda x, y, z, w: FakeFrontendSearchPipeline())

    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        access=project_pb2.ProjectAccess.MEMBERS_ONLY,
        project_id=12345)
    resp = self.call_api('issues_list', self.request).json_body
    self.assertEqual(2, int(resp['totalResults']))
    self.assertEqual(1, len(resp['items']))
    self.assertEqual(1, resp['items'][0]['id'])

  def testIssuesCommentsList_GetComments(self):
    """Get comments of requested issue."""

    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        project_id=12345)

    issue1 = fake.MakeTestIssue(
        project_id=12345, local_id=1, summary='test summary', status='New',
        issue_id=10001, owner_id=2, reporter_id=1)
    self.services.issue.TestAddIssue(issue1)

    comment = tracker_pb2.IssueComment(
        id=123, issue_id=10001,
        project_id=12345, user_id=2,
        content='this is a comment',
        timestamp=1437700000)
    self.services.issue.TestAddComment(comment, 1)

    resp = self.call_api('issues_comments_list', self.request).json_body
    self.assertEqual(2, resp['totalResults'])
    comment1 = resp['items'][0]
    comment2 = resp['items'][1]
    self.assertEqual('requester@example.com', comment1['author']['name'])
    self.assertEqual('test summary', comment1['content'])
    self.assertEqual('user@example.com', comment2['author']['name'])
    self.assertEqual('this is a comment', comment2['content'])

  def testIssuesCommentsInsert_NoCommentPermission(self):
    """No permission to comment an issue."""

    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        access=project_pb2.ProjectAccess.MEMBERS_ONLY,
        project_id=12345)

    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 2)
    self.services.issue.TestAddIssue(issue1)

    with self.call_should_fail(403):
      self.call_api('issues_comments_insert', self.request)

  def testIssuesCommentsInsert_Amendments(self):
    """Insert comments with amendments."""

    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        project_id=12345)

    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 2, project_name='test-project')
    issue2 = fake.MakeTestIssue(
        12345, 2, 'Issue 2', 'New', 2, project_name='test-project')
    issue3 = fake.MakeTestIssue(
        12345, 3, 'Issue 3', 'New', 2, project_name='test-project')
    self.services.issue.TestAddIssue(issue1)
    self.services.issue.TestAddIssue(issue2)
    self.services.issue.TestAddIssue(issue3)

    self.request['updates'] = {
        'summary': 'new summary',
        'status': 'Started',
        'owner': 'requester@example.com',
        'cc': ['user@example.com'],
        'labels': ['add_label', '-remove_label'],
        'blockedOn': ['2'],
        'blocking': ['3'],
        }
    resp = self.call_api('issues_comments_insert', self.request).json_body
    self.assertEqual('requester@example.com', resp['author']['name'])
    self.assertEqual('Updated', resp['updates']['status'])
    self.assertEqual(0, issue1.merged_into)

  def testIssuesCommentsInsert_MergeInto(self):
    """Insert comment that merges an issue into another issue."""

    self.services.project.TestAddProject(
        'test-project', owner_ids=[2], committer_ids=[1],
        project_id=12345)

    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 2, project_name='test-project')
    issue2 = fake.MakeTestIssue(
        12345, 2, 'Issue 2', 'New', 2, project_name='test-project')
    self.services.issue.TestAddIssue(issue1)
    self.services.issue.TestAddIssue(issue2)

    self.request['updates'] = {
        'summary': 'new summary',
        'status': 'Duplicate',
        'owner': 'requester@example.com',
        'cc': ['user@example.com'],
        'labels': ['add_label', '-remove_label'],
        'mergedInto': '2',
        }
    resp = self.call_api('issues_comments_insert', self.request).json_body
    self.assertEqual('requester@example.com', resp['author']['name'])
    self.assertEqual('Updated', resp['updates']['status'])
    self.assertEqual(issue2.issue_id, issue1.merged_into)
    issue2_comments = self.services.issue.GetCommentsForIssue(
      'cnxn', issue2.issue_id)
    self.assertEqual(2, len(issue2_comments))  # description and merge

  def testIssuesCommentInsert_CustomFields(self):
    """Update custom field values."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        project_id=12345)
    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 2,
        project_name='test-project')
    self.services.issue.TestAddIssue(issue1)
    self.SetUpFieldDefs(
        1, 12345, 'Field_int', tracker_pb2.FieldTypes.INT_TYPE)
    self.SetUpFieldDefs(
        2, 12345, 'Field_enum', tracker_pb2.FieldTypes.ENUM_TYPE)

    self.request['updates'] = {
        'fieldValues': [{'fieldName': 'Field_int', 'fieldValue': '11'},
                        {'fieldName': 'Field_enum', 'fieldValue': 'str'}]}
    resp = self.call_api('issues_comments_insert', self.request).json_body
    self.assertEqual('Updated', resp['updates']['status'])

  def testIssuesCommentInsert_MoveToProject_Fail(self):
    """Move issue to a different project and failed."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        project_id=12345)
    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 2, labels=['Restrict-View-Google'],
        project_name='test-project')
    self.services.issue.TestAddIssue(issue1)

    self.services.project.TestAddProject(
        'test-project2', owner_ids=[1],
        project_id=12346)
    issue2 = fake.MakeTestIssue(
        12346, 1, 'Issue 1', 'New', 2, project_name='test-project2')
    self.services.issue.TestAddIssue(issue2)

    # Project doesn't exist
    self.request['updates'] = {
        'moveToProject': 'not exist'}
    with self.call_should_fail(400):
      self.call_api('issues_comments_insert', self.request)

    # The issue is already in destination
    self.request['updates'] = {
        'moveToProject': 'test-project'}
    with self.call_should_fail(400):
      self.call_api('issues_comments_insert', self.request)

    # The user has no permission in test-project
    self.request['projectId'] = 'test-project2'
    self.request['updates'] = {
        'moveToProject': 'test-project'}
    with self.call_should_fail(400):
      self.call_api('issues_comments_insert', self.request)

    #  Restrict labels
    self.request['projectId'] = 'test-project'
    self.request['updates'] = {
        'moveToProject': 'test-project2'}
    with self.call_should_fail(400):
      self.call_api('issues_comments_insert', self.request)

  def testIssuesCommentInsert_MoveToProject_Normal(self):
    """Move issue."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[1, 2],
        project_id=12345)
    self.services.project.TestAddProject(
        'test-project2', owner_ids=[1, 2],
        project_id=12346)
    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 2, project_name='test-project')
    self.services.issue.TestAddIssue(issue1)
    issue2 = fake.MakeTestIssue(
        12346, 1, 'Issue 1', 'New', 2, project_name='test-project2')
    self.services.issue.TestAddIssue(issue2)

    self.request['updates'] = {
        'moveToProject': 'test-project2'}
    resp = self.call_api('issues_comments_insert', self.request).json_body

    self.assertEqual(
        'Moved issue test-project:1 to now be issue test-project:2.',
        resp['content'])

  def testIssuesCommentsDelete_NoComment(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        project_id=12345)
    issue1 = fake.MakeTestIssue(
        project_id=12345, local_id=1, summary='test summary',
        issue_id=10001, status='New', owner_id=2, reporter_id=2)
    self.services.issue.TestAddIssue(issue1)
    self.request['commentId'] = 1
    with self.call_should_fail(404):
      self.call_api('issues_comments_delete', self.request)

  def testIssuesCommentsDelete_NoDeletePermission(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        project_id=12345)
    issue1 = fake.MakeTestIssue(
        project_id=12345, local_id=1, summary='test summary',
        issue_id=10001, status='New', owner_id=2, reporter_id=2)
    self.services.issue.TestAddIssue(issue1)
    self.request['commentId'] = 0
    with self.call_should_fail(403):
      self.call_api('issues_comments_delete', self.request)

  def testIssuesCommentsDelete_DeleteUndelete(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        project_id=12345)
    issue1 = fake.MakeTestIssue(
        project_id=12345, local_id=1, summary='test summary',
        issue_id=10001, status='New', owner_id=2, reporter_id=1)
    self.services.issue.TestAddIssue(issue1)
    comment = tracker_pb2.IssueComment(
        id=123, issue_id=10001,
        project_id=12345, user_id=1,
        content='this is a comment',
        timestamp=1437700000)
    self.services.issue.TestAddComment(comment, 1)
    self.request['commentId'] = 1

    comments = self.services.issue.GetCommentsForIssue(None, 10001)

    self.call_api('issues_comments_delete', self.request)
    self.assertEqual(1, comments[1].deleted_by)

    self.call_api('issues_comments_undelete', self.request)
    self.assertIsNone(comments[1].deleted_by)

  def testGroupsSettingsList_AllSettings(self):
    resp = self.call_api('groups_settings_list', self.request).json_body
    all_settings = resp['groupSettings']
    self.assertEqual(1, len(all_settings))
    self.assertEqual('group@example.com', all_settings[0]['groupName'])

  def testGroupsSettingsList_ImportedSettings(self):
    self.services.user.TestAddUser('imported@example.com', 234)
    self.services.usergroup.TestAddGroupSettings(
        234, 'imported@example.com', external_group_type='mdb')
    self.request['importedGroupsOnly'] = True
    resp = self.call_api('groups_settings_list', self.request).json_body
    all_settings = resp['groupSettings']
    self.assertEqual(1, len(all_settings))
    self.assertEqual('imported@example.com', all_settings[0]['groupName'])

  def testGroupsCreate_NoPermission(self):
    self.request['groupName'] = 'group'
    with self.call_should_fail(403):
      self.call_api('groups_create', self.request)

  def SetUpGroupRequest(self, group_name, who_can_view_members='MEMBERS',
                        ext_group_type=None, perms=None,
                        requester='requester@example.com'):
    request = {
        'groupName': group_name,
        'requester': requester,
        'who_can_view_members': who_can_view_members,
        'ext_group_type': ext_group_type}
    self.request.pop("userId", None)
    self.mock(api_svc_v1.MonorailApi, 'mar_factory',
              lambda x, y: FakeMonorailApiRequest(
                  request, self.services, perms))
    return request

  def testGroupsCreate_Normal(self):
    request = self.SetUpGroupRequest('newgroup@example.com', 'MEMBERS',
                                     'MDB', permissions.ADMIN_PERMISSIONSET)

    resp = self.call_api('groups_create', request).json_body
    self.assertIn('groupID', resp)

  def testGroupsGet_NoPermission(self):
    request = self.SetUpGroupRequest('group@example.com')
    with self.call_should_fail(403):
      self.call_api('groups_get', request)

  def testGroupsGet_Normal(self):
    request = self.SetUpGroupRequest('group@example.com',
                                     perms=permissions.ADMIN_PERMISSIONSET)
    self.services.usergroup.TestAddMembers(123, [1], 'member')
    self.services.usergroup.TestAddMembers(123, [2], 'owner')
    resp = self.call_api('groups_get', request).json_body
    self.assertEqual(123, resp['groupID'])
    self.assertEqual(['requester@example.com'], resp['groupMembers'])
    self.assertEqual(['user@example.com'], resp['groupOwners'])
    self.assertEqual('group@example.com', resp['groupSettings']['groupName'])

  def testGroupsUpdate_NoPermission(self):
    request = self.SetUpGroupRequest('group@example.com')
    with self.call_should_fail(403):
      self.call_api('groups_update', request)

  def testGroupsUpdate_Normal(self):
    request = self.SetUpGroupRequest('group@example.com')
    request = self.SetUpGroupRequest('group@example.com',
                                     perms=permissions.ADMIN_PERMISSIONSET)
    request['last_sync_time'] = 123456789
    request['groupOwners'] = ['requester@example.com']
    request['groupMembers'] = ['user@example.com']
    resp = self.call_api('groups_update', request).json_body
    self.assertFalse(resp.get('error'))

  def testComponentsList(self):
    """Get components for a project."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')
    resp = self.call_api('components_list', self.request).json_body

    self.assertEqual(1, len(resp['components']))
    cd = resp['components'][0]
    self.assertEqual(1, cd['componentId'])
    self.assertEqual('API', cd['componentPath'])
    self.assertEqual(1, cd['componentId'])
    self.assertEqual('test-project', cd['projectName'])

  def testComponentsCreate_NoPermission(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')

    cd_dict = {
      'componentName': 'Test'}
    self.request.update(cd_dict)

    with self.call_should_fail(403):
      self.call_api('components_create', self.request)

  def testComponentsCreate_Invalid(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[1],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')

    # Component with invalid name
    cd_dict = {
      'componentName': 'c>d>e'}
    self.request.update(cd_dict)
    with self.call_should_fail(400):
      self.call_api('components_create', self.request)

    # Name already in use
    cd_dict = {
      'componentName': 'API'}
    self.request.update(cd_dict)
    with self.call_should_fail(400):
      self.call_api('components_create', self.request)

    # Parent component does not exist
    cd_dict = {
      'componentName': 'test',
      'parentPath': 'NotExist'}
    self.request.update(cd_dict)
    with self.call_should_fail(404):
      self.call_api('components_create', self.request)


  def testComponentsCreate_Normal(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[1],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')

    cd_dict = {
      'componentName': 'Test',
      'description':'test comp',
      'cc': ['requester@example.com']}
    self.request.update(cd_dict)

    resp = self.call_api('components_create', self.request).json_body
    self.assertEqual('test comp', resp['description'])
    self.assertEqual('requester@example.com', resp['creator'])
    self.assertEqual([u'requester@example.com'], resp['cc'])
    self.assertEqual('Test', resp['componentPath'])

    cd_dict = {
      'componentName': 'TestChild',
      'parentPath': 'API'}
    self.request.update(cd_dict)
    resp = self.call_api('components_create', self.request).json_body

    self.assertEqual('API>TestChild', resp['componentPath'])

  def testComponentsDelete_Invalid(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')

    # Fail to delete a non-existent component
    cd_dict = {
      'componentPath': 'NotExist'}
    self.request.update(cd_dict)
    with self.call_should_fail(404):
      self.call_api('components_delete', self.request)

    # The user has no permission to delete component
    cd_dict = {
      'componentPath': 'API'}
    self.request.update(cd_dict)
    with self.call_should_fail(403):
      self.call_api('components_delete', self.request)

    # The user tries to delete component that had subcomponents
    self.services.project.TestAddProject(
        'test-project2', owner_ids=[1],
        project_id=123456)
    self.SetUpComponents(123456, 1, 'Parent')
    self.SetUpComponents(123456, 2, 'Parent>Child')
    cd_dict = {
      'componentPath': 'Parent',
      'projectId': 'test-project2',}
    self.request.update(cd_dict)
    with self.call_should_fail(403):
      self.call_api('components_delete', self.request)

  def testComponentsDelete_Normal(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[1],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')

    cd_dict = {
      'componentPath': 'API'}
    self.request.update(cd_dict)
    _ = self.call_api('components_delete', self.request).json_body
    self.assertEqual(0, len(self.config.component_defs))

  def testComponentsUpdate_Invalid(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[2],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')
    self.SetUpComponents(12345, 2, 'Test', admin_ids=[1])

    # Fail to update a non-existent component
    cd_dict = {
      'componentPath': 'NotExist'}
    self.request.update(cd_dict)
    with self.call_should_fail(404):
      self.call_api('components_update', self.request)

    # The user has no permission to edit component
    cd_dict = {
      'componentPath': 'API'}
    self.request.update(cd_dict)
    with self.call_should_fail(403):
      self.call_api('components_update', self.request)

    # The user tries an invalid component name
    cd_dict = {
      'componentPath': 'Test',
      'updates': [{'field': 'LEAF_NAME', 'leafName': 'c>e'}]}
    self.request.update(cd_dict)
    with self.call_should_fail(400):
      self.call_api('components_update', self.request)

    # The user tries a name already in use
    cd_dict = {
      'componentPath': 'Test',
      'updates': [{'field': 'LEAF_NAME', 'leafName': 'API'}]}
    self.request.update(cd_dict)
    with self.call_should_fail(400):
      self.call_api('components_update', self.request)

  def testComponentsUpdate_Normal(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[1],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')
    self.SetUpComponents(12345, 2, 'Parent')
    self.SetUpComponents(12345, 3, 'Parent>Child')

    cd_dict = {
      'componentPath': 'API',
      'updates': [
          {'field': 'DESCRIPTION', 'description': ''},
          {'field': 'CC', 'cc': ['requester@example.com', 'user@example.com']},
          {'field': 'DEPRECATED', 'deprecated': True}]}
    self.request.update(cd_dict)
    _ = self.call_api('components_update', self.request).json_body
    component_def = tracker_bizobj.FindComponentDef(
        'API', self.config)
    self.assertIsNotNone(component_def)
    self.assertEqual('', component_def.docstring)
    self.assertEqual([1L, 2L], component_def.cc_ids)
    self.assertTrue(component_def.deprecated)

    cd_dict = {
      'componentPath': 'Parent',
      'updates': [
          {'field': 'LEAF_NAME', 'leafName': 'NewParent'}]}
    self.request.update(cd_dict)
    _ = self.call_api('components_update', self.request).json_body
    cd_parent = tracker_bizobj.FindComponentDef(
        'NewParent', self.config)
    cd_child = tracker_bizobj.FindComponentDef(
        'NewParent>Child', self.config)
    self.assertIsNotNone(cd_parent)
    self.assertIsNotNone(cd_child)


class RequestMock(object):

  def __init__(self):
    self.projectId = None
    self.issueId = None


class RequesterMock(object):

  def __init__(self, email=None):
    self._email = email

  def email(self):
    return self._email


class AllBaseChecksTest(unittest.TestCase):

  def setUp(self):
    self.services = MakeFakeServiceManager()
    self.services.user.TestAddUser('test@example.com', 1)
    self.services.project.TestAddProject(
        'test-project', owner_ids=[1], project_id=123,
        access=project_pb2.ProjectAccess.MEMBERS_ONLY)
    self.auth_client_ids = ['123456789.apps.googleusercontent.com']
    oauth.get_client_id = Mock(return_value=self.auth_client_ids[0])
    oauth.get_current_user = Mock(
        return_value=RequesterMock(email='test@example.com'))

  def testUnauthorizedRequester(self):
    with self.assertRaises(endpoints.UnauthorizedException):
      api_svc_v1.api_base_checks(None, None, None, None, [], [])

  def testNoUser(self):
    requester = RequesterMock(email='notexist@example.com')
    with self.assertRaises(user_svc.NoSuchUserException):
      api_svc_v1.api_base_checks(
          None, requester, self.services, None, self.auth_client_ids, [])

  def testNoOauthUser(self):
    oauth.get_current_user.side_effect = oauth.Error()
    with self.assertRaises(endpoints.UnauthorizedException):
      api_svc_v1.api_base_checks(
          None, None, self.services, None, [], [])

  def testBannedUser(self):
    banned_email = 'banned@example.com'
    self.services.user.TestAddUser(banned_email, 2, banned=True)
    requester = RequesterMock(email=banned_email)
    with self.assertRaises(permissions.BannedUserException):
      api_svc_v1.api_base_checks(
          None, requester, self.services, None, self.auth_client_ids, [])

  def testNoProject(self):
    request = RequestMock()
    request.projectId = 'notexist-project'
    requester = RequesterMock(email='test@example.com')
    with self.assertRaises(project_svc.NoSuchProjectException):
      api_svc_v1.api_base_checks(
          request, requester, self.services, None, self.auth_client_ids, [])

  def testNonLiveProject(self):
    archived_project = 'archived-project'
    self.services.project.TestAddProject(
        archived_project, owner_ids=[1],
        state=project_pb2.ProjectState.ARCHIVED)
    request = RequestMock()
    request.projectId = archived_project
    requester = RequesterMock(email='test@example.com')
    with self.assertRaises(permissions.PermissionException):
      api_svc_v1.api_base_checks(
          request, requester, self.services, None, self.auth_client_ids, [])

  def testNoViewProjectPermission(self):
    nonmember_email = 'nonmember@example.com'
    self.services.user.TestAddUser(nonmember_email, 2)
    requester = RequesterMock(email=nonmember_email)
    request = RequestMock()
    request.projectId = 'test-project'
    with self.assertRaises(permissions.PermissionException):
      api_svc_v1.api_base_checks(
          request, requester, self.services, None, self.auth_client_ids, [])

  def testAllPass(self):
    requester = RequesterMock(email='test@example.com')
    request = RequestMock()
    request.projectId = 'test-project'
    api_svc_v1.api_base_checks(
        request, requester, self.services, None, self.auth_client_ids, [])

  def testNoIssue(self):
    requester = RequesterMock(email='test@example.com')
    request = RequestMock()
    request.projectId = 'test-project'
    request.issueId = 12345
    with self.assertRaises(issue_svc.NoSuchIssueException):
      api_svc_v1.api_base_checks(
          request, requester, self.services, None, self.auth_client_ids, [])

  def testNoViewIssuePermission(self):
    requester = RequesterMock(email='test@example.com')
    request = RequestMock()
    request.projectId = 'test-project'
    request.issueId = 1
    issue1 = fake.MakeTestIssue(
        project_id=123, local_id=1, summary='test summary',
        status='New', owner_id=1, reporter_id=1)
    issue1.deleted = True
    self.services.issue.TestAddIssue(issue1)
    with self.assertRaises(permissions.PermissionException):
      api_svc_v1.api_base_checks(
          request, requester, self.services, None, self.auth_client_ids, [])

  def testAnonymousClients(self):
    oauth.get_client_id = Mock(return_value='anonymous')
    requester = RequesterMock(email='test@example.com')
    request = RequestMock()
    request.projectId = 'test-project'
    api_svc_v1.api_base_checks(
        request, requester, self.services, None, [], ['test@example.com'])

    with self.assertRaises(endpoints.UnauthorizedException):
      api_svc_v1.api_base_checks(
          request, requester, self.services, None, [], [])
