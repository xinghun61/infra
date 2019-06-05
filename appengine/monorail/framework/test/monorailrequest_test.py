# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the monorailrequest module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import endpoints
import mock
import re
import unittest

import mox

from google.appengine.api import oauth
from google.appengine.api import users

import webapp2

from framework import exceptions
from framework import monorailrequest
from framework import permissions
from proto import project_pb2
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import tracker_constants


class HostportReTest(unittest.TestCase):

  def testGood(self):
    test_data = [
      'localhost:8080',
      'app.appspot.com',
      'bugs-staging.chromium.org',
      'vers10n-h3x-dot-app-id.appspot.com',
      ]
    for hostport in test_data:
      self.assertTrue(monorailrequest._HOSTPORT_RE.match(hostport),
                      msg='Incorrectly rejected %r' % hostport)

  def testBad(self):
    test_data = [
      '',
      ' ',
      '\t',
      '\n',
      '\'',
      '"',
      'version"cruft-dot-app-id.appspot.com',
      '\nother header',
      'version&cruft-dot-app-id.appspot.com',
      ]
    for hostport in test_data:
      self.assertFalse(monorailrequest._HOSTPORT_RE.match(hostport),
                       msg='Incorrectly accepted %r' % hostport)


class MonorailApiRequestUnitTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        project=fake.ProjectService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService())
    self.project = self.services.project.TestAddProject(
        'proj', project_id=789)
    self.services.user.TestAddUser('requester@example.com', 111)
    self.issue = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111)
    self.services.issue.TestAddIssue(self.issue)

    self.patcher_1 = mock.patch('endpoints.get_current_user')
    self.mock_endpoints_gcu = self.patcher_1.start()
    self.mock_endpoints_gcu.return_value = None
    self.patcher_2 = mock.patch('google.appengine.api.oauth.get_current_user')
    self.mock_oauth_gcu = self.patcher_2.start()
    self.mock_oauth_gcu.return_value = testing_helpers.Blank(
        email=lambda: 'requester@example.com')

  def tearDown(self):
    mock.patch.stopall()

  def testInit_NoProjectIssueOrViewedUser(self):
    request = testing_helpers.Blank()
    mar = monorailrequest.MonorailApiRequest(
        request, self.services, cnxn=self.cnxn)
    self.assertIsNone(mar.project)
    self.assertIsNone(mar.issue)

  def testInit_WithProject(self):
    request = testing_helpers.Blank(projectId='proj')
    mar = monorailrequest.MonorailApiRequest(
        request, self.services, cnxn=self.cnxn)
    self.assertEqual(self.project, mar.project)
    self.assertIsNone(mar.issue)

  def testInit_WithProjectAndIssue(self):
    request = testing_helpers.Blank(
        projectId='proj', issueId=1)
    mar = monorailrequest.MonorailApiRequest(
        request, self.services, cnxn=self.cnxn)
    self.assertEqual(self.project, mar.project)
    self.assertEqual(self.issue, mar.issue)

  def testGetParam_Normal(self):
    request = testing_helpers.Blank(q='owner:me')
    mar = monorailrequest.MonorailApiRequest(
        request, self.services, cnxn=self.cnxn)
    self.assertEqual(None, mar.GetParam('unknown'))
    self.assertEqual(100, mar.GetParam('num'))
    self.assertEqual('owner:me', mar.GetParam('q'))

    request = testing_helpers.Blank(q='owner:me', maxResults=200)
    mar = monorailrequest.MonorailApiRequest(
        request, self.services, cnxn=self.cnxn)
    self.assertEqual(200, mar.GetParam('num'))


class MonorailRequestUnitTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        features=fake.FeaturesService())
    self.project = self.services.project.TestAddProject('proj')
    self.hotlist = self.services.features.TestAddHotlist(
        'TestHotlist', owner_ids=[111])
    self.services.user.TestAddUser('jrobbins@example.com', 111)

    self.mox = mox.Mox()
    self.mox.StubOutWithMock(users, 'get_current_user')
    users.get_current_user().AndReturn(None)
    self.mox.ReplayAll()

  def tearDown(self):
    self.mox.UnsetStubs()

  def testGetIntParam_ConvertsQueryParamToInt(self):
    notice_id = 12345
    mr = testing_helpers.MakeMonorailRequest(
        path='/foo?notice=%s' % notice_id)

    value = mr.GetIntParam('notice')
    self.assert_(isinstance(value, int))
    self.assertEqual(notice_id, value)

  def testGetIntParam_ConvertsQueryParamToLong(self):
    notice_id = 12345678901234567890
    mr = testing_helpers.MakeMonorailRequest(
        path='/foo?notice=%s' % notice_id)

    value = mr.GetIntParam('notice')
    self.assertTrue(isinstance(value, long))
    self.assertEqual(notice_id, value)

  def testGetIntListParam_NoParam(self):
    mr = monorailrequest.MonorailRequest(self.services)
    mr.ParseRequest(webapp2.Request.blank('servlet'), self.services)
    self.assertEqual(mr.GetIntListParam('ids'), None)
    self.assertEqual(mr.GetIntListParam('ids', default_value=['test']),
                      ['test'])

  def testGetIntListParam_OneValue(self):
    mr = monorailrequest.MonorailRequest(self.services)
    mr.ParseRequest(webapp2.Request.blank('servlet?ids=11'), self.services)
    self.assertEqual(mr.GetIntListParam('ids'), [11])
    self.assertEqual(mr.GetIntListParam('ids', default_value=['test']),
                      [11])

  def testGetIntListParam_MultiValue(self):
    mr = monorailrequest.MonorailRequest(self.services)
    mr.ParseRequest(
        webapp2.Request.blank('servlet?ids=21,22,23'), self.services)
    self.assertEqual(mr.GetIntListParam('ids'), [21, 22, 23])
    self.assertEqual(mr.GetIntListParam('ids', default_value=['test']),
                      [21, 22, 23])

  def testGetIntListParam_BogusValue(self):
    mr = monorailrequest.MonorailRequest(self.services)
    with self.assertRaises(exceptions.InputException):
      mr.ParseRequest(
          webapp2.Request.blank('servlet?ids=not_an_int'), self.services)

  def testGetIntListParam_Malformed(self):
    mr = monorailrequest.MonorailRequest(self.services)
    with self.assertRaises(exceptions.InputException):
      mr.ParseRequest(
          webapp2.Request.blank('servlet?ids=31,32,,'), self.services)

  def testDefaultValuesNoUrl(self):
    """If request has no param, default param values should be used."""
    mr = monorailrequest.MonorailRequest(self.services)
    mr.ParseRequest(webapp2.Request.blank('servlet'), self.services)
    self.assertEqual(mr.GetParam('r', 3), 3)
    self.assertEqual(mr.GetIntParam('r', 3), 3)
    self.assertEqual(mr.GetPositiveIntParam('r', 3), 3)
    self.assertEqual(mr.GetIntListParam('r', [3, 4]), [3, 4])

  def _MRWithMockRequest(
      self, path, headers=None, *mr_args, **mr_kwargs):
    request = webapp2.Request.blank(path, headers=headers)
    mr = monorailrequest.MonorailRequest(self.services, *mr_args, **mr_kwargs)
    mr.ParseRequest(request, self.services)
    return mr

  def testParseQueryParameters(self):
    mr = self._MRWithMockRequest(
        '/p/proj/issues/list?q=foo+OR+bar&num=50')
    self.assertEqual('foo OR bar', mr.query)
    self.assertEqual(50, mr.num)

  def testParseQueryParameters_ModeMissing(self):
    mr = self._MRWithMockRequest(
        '/p/proj/issues/list?q=foo+OR+bar&num=50')
    self.assertEqual('list', mr.mode)

  def testParseQueryParameters_ModeList(self):
    mr = self._MRWithMockRequest(
        '/p/proj/issues/list?q=foo+OR+bar&num=50&mode=')
    self.assertEqual('list', mr.mode)

  def testParseQueryParameters_ModeGrid(self):
    mr = self._MRWithMockRequest(
        '/p/proj/issues/list?q=foo+OR+bar&num=50&mode=grid')
    self.assertEqual('grid', mr.mode)

  def testParseQueryParameters_ModeChart(self):
    mr = self._MRWithMockRequest(
        '/p/proj/issues/list?q=foo+OR+bar&num=50&mode=chart')
    self.assertEqual('chart', mr.mode)

  def testParseRequest_Scheme(self):
    mr = self._MRWithMockRequest('/p/proj/')
    self.assertEqual('http', mr.request.scheme)

  def testParseRequest_HostportAndCurrentPageURL(self):
    mr = self._MRWithMockRequest('/p/proj/', headers={
        'Host': 'example.com',
        'Cookie': 'asdf',
        })
    self.assertEqual('http', mr.request.scheme)
    self.assertEqual('example.com', mr.request.host)
    self.assertEqual('http://example.com/p/proj/', mr.current_page_url)

  def testParseRequest_ProjectFound(self):
    mr = self._MRWithMockRequest('/p/proj/')
    self.assertEqual(mr.project, self.project)

  def testParseRequest_ProjectNotFound(self):
    with self.assertRaises(exceptions.NoSuchProjectException):
      self._MRWithMockRequest('/p/no-such-proj/')

  def testViewedUser_WithEmail(self):
    mr = self._MRWithMockRequest('/u/jrobbins@example.com/')
    self.assertEqual('jrobbins@example.com', mr.viewed_username)
    self.assertEqual(111, mr.viewed_user_auth.user_id)
    self.assertEqual(
        self.services.user.GetUser('fake cnxn', 111),
        mr.viewed_user_auth.user_pb)

  def testViewedUser_WithUserID(self):
    mr = self._MRWithMockRequest('/u/111/')
    self.assertEqual('jrobbins@example.com', mr.viewed_username)
    self.assertEqual(111, mr.viewed_user_auth.user_id)
    self.assertEqual(
        self.services.user.GetUser('fake cnxn', 111),
        mr.viewed_user_auth.user_pb)

  def testViewedUser_NoSuchEmail(self):
    with self.assertRaises(webapp2.HTTPException) as cm:
      self._MRWithMockRequest('/u/unknownuser@example.com/')
    self.assertEqual(404, cm.exception.code)

  def testViewedUser_NoSuchUserID(self):
    with self.assertRaises(exceptions.NoSuchUserException):
      self._MRWithMockRequest('/u/234521111/')

  def testGetParam(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/foo?syn=error!&a=a&empty=',
        params=dict(over1='over_value1', over2='over_value2'))

    # test tampering
    self.assertRaises(exceptions.InputException, mr.GetParam, 'a',
                      antitamper_re=re.compile(r'^$'))
    self.assertRaises(exceptions.InputException, mr.GetParam,
                      'undefined', default_value='default',
                      antitamper_re=re.compile(r'^$'))

    # test empty value
    self.assertEqual('', mr.GetParam(
        'empty', default_value='default', antitamper_re=re.compile(r'^$')))

    # test default
    self.assertEqual('default', mr.GetParam(
        'undefined', default_value='default'))

  def testComputeColSpec(self):
    # No config passed, and nothing in URL
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/detail?id=123')
    mr.ComputeColSpec(None)
    self.assertEqual(tracker_constants.DEFAULT_COL_SPEC, mr.col_spec)

    # No config passed, but set in URL
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/detail?id=123&colspec=a b C')
    mr.ComputeColSpec(None)
    self.assertEqual('a b C', mr.col_spec)

    config = tracker_pb2.ProjectIssueConfig()

    # No default in the config, and nothing in URL
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/detail?id=123')
    mr.ComputeColSpec(config)
    self.assertEqual(tracker_constants.DEFAULT_COL_SPEC, mr.col_spec)

    # No default in the config, but set in URL
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/detail?id=123&colspec=a b C')
    mr.ComputeColSpec(config)
    self.assertEqual('a b C', mr.col_spec)

    config.default_col_spec = 'd e f'

    # Default in the config, and nothing in URL
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/detail?id=123')
    mr.ComputeColSpec(config)
    self.assertEqual('d e f', mr.col_spec)

    # Default in the config, but overrided via URL
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/detail?id=123&colspec=a b C')
    mr.ComputeColSpec(config)
    self.assertEqual('a b C', mr.col_spec)

    # project colspec contains hotlist columns
    mr = testing_helpers.MakeMonorailRequest(
        path='p/proj/issues/detail?id=123&colspec=Rank Adder Adder Owner')
    mr.ComputeColSpec(None)
    self.assertEqual(tracker_constants.DEFAULT_COL_SPEC, mr.col_spec)

    # hotlist columns are not deleted when page is a hotlist page
    mr = testing_helpers.MakeMonorailRequest(
        path='u/jrobbins@example.com/hotlists/TestHotlist?colspec=Rank Adder',
        hotlist=self.hotlist)
    mr.ComputeColSpec(None)
    self.assertEqual('Rank Adder', mr.col_spec)

  def testComputeColSpec_XSS(self):
    config_1 = tracker_pb2.ProjectIssueConfig()
    config_2 = tracker_pb2.ProjectIssueConfig()
    config_2.default_col_spec = "id '+alert(1)+'"
    mr_1 = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/detail?id=123')
    mr_2 = testing_helpers.MakeMonorailRequest(
        path="/p/proj/issues/detail?id=123&colspec=id '+alert(1)+'")

    # Normal colspec in config but malicious request
    self.assertRaises(
        exceptions.InputException,
        mr_2.ComputeColSpec, config_1)

    # Malicious colspec in config but normal request
    self.assertRaises(
        exceptions.InputException,
        mr_1.ComputeColSpec, config_2)

    # Malicious colspec in config and malicious request
    self.assertRaises(
        exceptions.InputException,
        mr_2.ComputeColSpec, config_2)


class CalcDefaultQueryTest(unittest.TestCase):

  def setUp(self):
    self.project = project_pb2.Project()
    self.project.project_name = 'proj'
    self.project.owner_ids = [111]
    self.config = tracker_pb2.ProjectIssueConfig()

  def testIssueListURL_NotDefaultCan(self):
    mr = monorailrequest.MonorailRequest(None)
    mr.query = None
    mr.can = 1
    self.assertEqual('', mr._CalcDefaultQuery())

  def testIssueListURL_NoProject(self):
    mr = monorailrequest.MonorailRequest(None)
    mr.query = None
    mr.can = 2
    self.assertEqual('', mr._CalcDefaultQuery())

  def testIssueListURL_NoConfig(self):
    mr = monorailrequest.MonorailRequest(None)
    mr.query = None
    mr.can = 2
    mr.project = self.project
    self.assertEqual('', mr._CalcDefaultQuery())

  def testIssueListURL_NotCustomized(self):
    mr = monorailrequest.MonorailRequest(None)
    mr.query = None
    mr.can = 2
    mr.project = self.project
    mr.config = self.config
    self.assertEqual('', mr._CalcDefaultQuery())

  def testIssueListURL_Customized_Nonmember(self):
    mr = monorailrequest.MonorailRequest(None)
    mr.query = None
    mr.can = 2
    mr.project = self.project
    mr.config = self.config
    mr.config.member_default_query = 'owner:me'
    self.assertEqual('', mr._CalcDefaultQuery())

    mr.auth = testing_helpers.Blank(effective_ids=set())
    self.assertEqual('', mr._CalcDefaultQuery())

    mr.auth = testing_helpers.Blank(effective_ids={999})
    self.assertEqual('', mr._CalcDefaultQuery())

  def testIssueListURL_Customized_Member(self):
    mr = monorailrequest.MonorailRequest(None)
    mr.query = None
    mr.can = 2
    mr.project = self.project
    mr.config = self.config
    mr.config.member_default_query = 'owner:me'
    mr.auth = testing_helpers.Blank(effective_ids={111})
    self.assertEqual('owner:me', mr._CalcDefaultQuery())


class TestMonorailRequestFunctions(unittest.TestCase):

  def testExtractPathIdentifiers_ProjectOnly(self):
    (username, project_name, hotlist_id,
     hotlist_name) = monorailrequest._ParsePathIdentifiers(
         '/p/proj/issues/list?q=foo+OR+bar&ts=1234')
    self.assertIsNone(username)
    self.assertIsNone(hotlist_id)
    self.assertIsNone(hotlist_name)
    self.assertEqual('proj', project_name)

  def testExtractPathIdentifiers_ViewedUserOnly(self):
    (username, project_name, hotlist_id,
     hotlist_name) = monorailrequest._ParsePathIdentifiers(
         '/u/jrobbins@example.com/')
    self.assertEqual('jrobbins@example.com', username)
    self.assertIsNone(project_name)
    self.assertIsNone(hotlist_id)
    self.assertIsNone(hotlist_name)

  def testExtractPathIdentifiers_ViewedUserURLSpace(self):
    (username, project_name, hotlist_id,
     hotlist_name) = monorailrequest._ParsePathIdentifiers(
         '/u/jrobbins@example.com/updates')
    self.assertEqual('jrobbins@example.com', username)
    self.assertIsNone(project_name)
    self.assertIsNone(hotlist_id)
    self.assertIsNone(hotlist_name)

  def testExtractPathIdentifiers_ViewedGroupURLSpace(self):
    (username, project_name, hotlist_id,
     hotlist_name) = monorailrequest._ParsePathIdentifiers(
        '/g/user-group@example.com/updates')
    self.assertEqual('user-group@example.com', username)
    self.assertIsNone(project_name)
    self.assertIsNone(hotlist_id)
    self.assertIsNone(hotlist_name)

  def testExtractPathIdentifiers_HotlistIssuesURLSpaceById(self):
    (username, project_name, hotlist_id,
     hotlist_name) = monorailrequest._ParsePathIdentifiers(
         '/u/jrobbins@example.com/hotlists/13124?q=stuff&ts=more')
    self.assertIsNone(hotlist_name)
    self.assertIsNone(project_name)
    self.assertEqual('jrobbins@example.com', username)
    self.assertEqual(13124, hotlist_id)

  def testExtractPathIdentifiers_HotlistIssuesURLSpaceByName(self):
    (username, project_name, hotlist_id,
     hotlist_name) = monorailrequest._ParsePathIdentifiers(
         '/u/jrobbins@example.com/hotlists/testname?q=stuff&ts=more')
    self.assertIsNone(project_name)
    self.assertIsNone(hotlist_id)
    self.assertEqual('jrobbins@example.com', username)
    self.assertEqual('testname', hotlist_name)

  def testParseColSpec(self):
    parse = monorailrequest.ParseColSpec
    self.assertEqual(['PageName', 'Summary', 'Changed', 'ChangedBy'],
                     parse(u'PageName Summary Changed ChangedBy'))
    self.assertEqual(['Foo-Bar', 'Foo-Bar-Baz', 'Release-1.2', 'Hey', 'There'],
                     parse('Foo-Bar Foo-Bar-Baz Release-1.2 Hey!There'))
    self.assertEqual(
        ['\xe7\xaa\xbf\xe8\x8b\xa5\xe7\xb9\xb9'.decode('utf-8'),
         '\xe5\x9f\xba\xe5\x9c\xb0\xe3\x81\xaf'.decode('utf-8')],
        parse('\xe7\xaa\xbf\xe8\x8b\xa5\xe7\xb9\xb9 '
              '\xe5\x9f\xba\xe5\x9c\xb0\xe3\x81\xaf'.decode('utf-8')))

  def testParseColSpec_Dedup(self):
    """An attacker cannot inflate response size by repeating a column."""
    parse = monorailrequest.ParseColSpec
    self.assertEqual([], parse(''))
    self.assertEqual(
      ['Aa', 'b', 'c/d'],
      parse(u'Aa Aa AA AA AA b Aa aa c/d d c aA b aa B C/D D/aa/c'))
    self.assertEqual(
      ['A', 'b', 'c/d', 'e', 'f'],
      parse(u'A b c/d e f g h i j a/k l m/c/a n/o'))

  def testParseColSpec_Huge(self):
    """An attacker cannot inflate response size with a huge column name."""
    parse = monorailrequest.ParseColSpec
    self.assertEqual(
      ['Aa', 'b', 'c/d'],
      parse(u'Aa Aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa b c/d'))

  def testParseColSpec_Ignore(self):
    """We ignore groupby and grid axes that would be useless."""
    parse = monorailrequest.ParseColSpec
    self.assertEqual(
      ['Aa', 'b', 'c/d'],
      parse(u'Aa AllLabels alllabels Id b opened/summary c/d',
            ignore=tracker_constants.NOT_USED_IN_GRID_AXES))


class TestPermissionLookup(unittest.TestCase):
  OWNER_ID = 1
  OTHER_USER_ID = 2

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService())
    self.services.user.TestAddUser('owner@gmail.com', self.OWNER_ID)
    self.services.user.TestAddUser('user@gmail.com', self.OTHER_USER_ID)
    self.live_project = self.services.project.TestAddProject(
        'live', owner_ids=[self.OWNER_ID])
    self.archived_project = self.services.project.TestAddProject(
        'archived', owner_ids=[self.OWNER_ID],
        state=project_pb2.ProjectState.ARCHIVED)
    self.members_only_project = self.services.project.TestAddProject(
        'members-only', owner_ids=[self.OWNER_ID],
        access=project_pb2.ProjectAccess.MEMBERS_ONLY)

    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()

  def CheckPermissions(self, perms, expect_view, expect_commit, expect_edit):
    may_view = perms.HasPerm(permissions.VIEW, None, None)
    self.assertEqual(expect_view, may_view)
    may_commit = perms.HasPerm(permissions.COMMIT, None, None)
    self.assertEqual(expect_commit, may_commit)
    may_edit = perms.HasPerm(permissions.EDIT_PROJECT, None, None)
    self.assertEqual(expect_edit, may_edit)

  def MakeRequestAsUser(self, project_name, email):
    self.mox.StubOutWithMock(users, 'get_current_user')
    users.get_current_user().AndReturn(testing_helpers.Blank(
        email=lambda: email))
    self.mox.ReplayAll()

    request = webapp2.Request.blank('/p/' + project_name)
    mr = monorailrequest.MonorailRequest(self.services)
    with mr.profiler.Phase('parse user info'):
      mr.ParseRequest(request, self.services)
      print('mr.auth is %r' % mr.auth)
    return mr

  def testOwnerPermissions_Live(self):
    mr = self.MakeRequestAsUser('live', 'owner@gmail.com')
    self.CheckPermissions(mr.perms, True, True, True)

  def testOwnerPermissions_Archived(self):
    mr = self.MakeRequestAsUser('archived', 'owner@gmail.com')
    self.CheckPermissions(mr.perms, True, False, True)

  def testOwnerPermissions_MembersOnly(self):
    mr = self.MakeRequestAsUser('members-only', 'owner@gmail.com')
    self.CheckPermissions(mr.perms, True, True, True)

  def testExternalUserPermissions_Live(self):
    mr = self.MakeRequestAsUser('live', 'user@gmail.com')
    self.CheckPermissions(mr.perms, True, False, False)

  def testExternalUserPermissions_Archived(self):
    mr = self.MakeRequestAsUser('archived', 'user@gmail.com')
    self.CheckPermissions(mr.perms, False, False, False)

  def testExternalUserPermissions_MembersOnly(self):
    mr = self.MakeRequestAsUser('members-only', 'user@gmail.com')
    self.CheckPermissions(mr.perms, False, False, False)
