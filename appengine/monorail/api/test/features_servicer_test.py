# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the projects servicer."""

import unittest

import mox
from components.prpc import codes
from components.prpc import context
from components.prpc import server

from api import converters
from api import features_servicer
from api.api_proto import common_pb2
from api.api_proto import features_pb2
from api.api_proto import features_objects_pb2
from framework import authdata
from framework import exceptions
from framework import monorailcontext
from framework import permissions
from testing import fake
from tracker import tracker_bizobj
from services import service_manager


class FeaturesServicerTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = fake.MonorailConnection()
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService(),
        features=fake.FeaturesService(),
        hotlist_star=fake.HotlistStarService())
    self.project = self.services.project.TestAddProject(
        'proj', project_id=789, owner_ids=[111L], contrib_ids=[222L, 333L])
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.user = self.services.user.TestAddUser('owner@example.com', 111L)
    self.user = self.services.user.TestAddUser('editor@example.com', 222L)
    self.user = self.services.user.TestAddUser('foo@example.com', 333L)
    self.user = self.services.user.TestAddUser('bar@example.com', 444L)
    self.features_svcr = features_servicer.FeaturesServicer(
        self.services, make_rate_limiter=False)
    self.prpc_context = context.ServicerContext()
    self.prpc_context.set_code(codes.StatusCode.OK)
    self.issue_1 = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111L, project_name='proj')
    self.issue_2 = fake.MakeTestIssue(
        789, 2, 'sum', 'New', 111L, project_name='proj')
    self.services.issue.TestAddIssue(self.issue_1)
    self.services.issue.TestAddIssue(self.issue_2)

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def CallWrapped(self, wrapped_handler, *args, **kwargs):
    return wrapped_handler.wrapped(self.features_svcr, *args, **kwargs)

  def testListHotlistsByUser_SearchByEmail(self):
    """We can get a list of hotlists for a given email."""
    # Public hostlist owned by 'owner@example.com'
    self.services.features.CreateHotlist(
        self.cnxn, 'Fake Hotlist', 'Summary', 'Description',
        owner_ids=[111L], editor_ids=[222L])

    # Query for issues for 'owner@example.com'
    user_ref = common_pb2.UserRef(display_name='owner@example.com')
    request = features_pb2.ListHotlistsByUserRequest(user=user_ref)

    # We're authenticated as 'foo@example.com'
    mc = monorailcontext.MonorailContext(self.services, cnxn=self.cnxn)

    response = self.CallWrapped(self.features_svcr.ListHotlistsByUser, mc,
                                request)
    self.assertEqual(1, len(response.hotlists))
    hotlist = response.hotlists[0]
    self.assertEqual(111L, hotlist.owner_ref.user_id)
    self.assertEqual('ow...@example.com', hotlist.owner_ref.display_name)
    self.assertEqual('Fake Hotlist', hotlist.name)
    self.assertEqual('Summary', hotlist.summary)
    self.assertEqual('Description', hotlist.description)

  def testListHotlistsByUser_SearchByOwner(self):
    """We can get a list of hotlists for a given user."""
    # Public hostlist owned by 'owner@example.com'
    self.services.features.CreateHotlist(
        self.cnxn, 'Fake Hotlist', 'Summary', 'Description',
        owner_ids=[111L], editor_ids=[222L])

    # Query for issues for 'owner@example.com'
    user_ref = common_pb2.UserRef(user_id=111L)
    request = features_pb2.ListHotlistsByUserRequest(user=user_ref)

    # We're authenticated as 'foo@example.com'
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.com')

    response = self.CallWrapped(self.features_svcr.ListHotlistsByUser, mc,
                                request)
    self.assertEqual(1, len(response.hotlists))
    hotlist = response.hotlists[0]
    self.assertEqual(111L, hotlist.owner_ref.user_id)
    self.assertEqual('ow...@example.com', hotlist.owner_ref.display_name)
    self.assertEqual('Fake Hotlist', hotlist.name)
    self.assertEqual('Summary', hotlist.summary)
    self.assertEqual('Description', hotlist.description)

  def testListHotlistsByUser_SearchByEditor(self):
    """We can get a list of hotlists for a given user."""
    # Public hostlist owned by 'owner@example.com'
    self.services.features.CreateHotlist(
        self.cnxn, 'Fake Hotlist', 'Summary', 'Description',
        owner_ids=[111L], editor_ids=[222L])

    # Query for issues for 'editor@example.com'
    user_ref = common_pb2.UserRef(user_id=222L)
    request = features_pb2.ListHotlistsByUserRequest(user=user_ref)

    # We're authenticated as 'foo@example.com'
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.com')

    response = self.CallWrapped(self.features_svcr.ListHotlistsByUser, mc,
                                request)
    self.assertEqual(1, len(response.hotlists))
    hotlist = response.hotlists[0]
    self.assertEqual(111L, hotlist.owner_ref.user_id)
    self.assertEqual('ow...@example.com', hotlist.owner_ref.display_name)
    self.assertEqual('Fake Hotlist', hotlist.name)
    self.assertEqual('Summary', hotlist.summary)
    self.assertEqual('Description', hotlist.description)

  def testListHotlistsByUser_NotSignedIn(self):
    # Public hostlist owned by 'owner@example.com'
    self.services.features.CreateHotlist(
        self.cnxn, 'Fake Hotlist', 'Summary', 'Description',
        owner_ids=[111L], editor_ids=[222L])

    # Query for issues for 'owner@example.com'
    user_ref = common_pb2.UserRef(user_id=111L)
    request = features_pb2.ListHotlistsByUserRequest(user=user_ref)

    # We're not authenticated
    mc = monorailcontext.MonorailContext(self.services, cnxn=self.cnxn)
    response = self.CallWrapped(self.features_svcr.ListHotlistsByUser, mc,
                                request)

    self.assertEqual(1, len(response.hotlists))
    hotlist = response.hotlists[0]
    self.assertEqual(111L, hotlist.owner_ref.user_id)

  def testListHotlistsByUser_Empty(self):
    """There are no hotlists for the given user."""
    # Public hostlist owned by 'owner@example.com'
    self.services.features.CreateHotlist(
        self.cnxn, 'Fake Hotlist', 'Summary', 'Description',
        owner_ids=[111L], editor_ids=[222L])

    # Query for issues for 'bar@example.com'
    user_ref = common_pb2.UserRef(user_id=444L)
    request = features_pb2.ListHotlistsByUserRequest(user=user_ref)

    # We're authenticated as 'foo@example.com'
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.com')
    response = self.CallWrapped(self.features_svcr.ListHotlistsByUser, mc,
                                request)

    self.assertEqual(0, len(response.hotlists))

  def testListHotlistsByUser_NoHotlists(self):
    """We can get a list of all projects on the site."""
    # No hotlists
    # Query for issues for 'owner@example.com'
    user_ref = common_pb2.UserRef(user_id=111L)
    request = features_pb2.ListHotlistsByUserRequest(user=user_ref)

    # We're authenticated as 'foo@example.com'
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.com')
    response = self.CallWrapped(self.features_svcr.ListHotlistsByUser, mc,
                                request)
    self.assertEqual(0, len(response.hotlists))

  def testListHotlistsByUser_PrivateIssueAsOwner(self):
    # Private hostlist owned by 'owner@example.com'
    self.services.features.CreateHotlist(
        self.cnxn, 'Fake Hotlist', 'Summary', 'Description',
        owner_ids=[111L], editor_ids=[222L], is_private=True)

    # Query for issues for 'owner@example.com'
    user_ref = common_pb2.UserRef(user_id=111L)
    request = features_pb2.ListHotlistsByUserRequest(user=user_ref)

    # We're authenticated as 'owner@example.com'
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.features_svcr.ListHotlistsByUser, mc,
                                request)

    self.assertEqual(1, len(response.hotlists))
    hotlist = response.hotlists[0]
    self.assertEqual(111L, hotlist.owner_ref.user_id)

  def testListHotlistsByUser_PrivateIssueAsEditor(self):
    # Private hostlist owned by 'owner@example.com'
    self.services.features.CreateHotlist(
        self.cnxn, 'Fake Hotlist', 'Summary', 'Description',
        owner_ids=[111L], editor_ids=[222L], is_private=True)

    # Query for issues for 'owner@example.com'
    user_ref = common_pb2.UserRef(user_id=111L)
    request = features_pb2.ListHotlistsByUserRequest(user=user_ref)

    # We're authenticated as 'editor@example.com'
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='editor@example.com')
    response = self.CallWrapped(self.features_svcr.ListHotlistsByUser, mc,
                                request)

    self.assertEqual(1, len(response.hotlists))
    hotlist = response.hotlists[0]
    self.assertEqual(111L, hotlist.owner_ref.user_id)

  def testListHotlistsByUser_PrivateIssueNoAccess(self):
    # Private hostlist owned by 'owner@example.com'
    self.services.features.CreateHotlist(
        self.cnxn, 'Fake Hotlist', 'Summary', 'Description',
        owner_ids=[111L], editor_ids=[222L], is_private=True)

    # Query for issues for 'owner@example.com'
    user_ref = common_pb2.UserRef(user_id=111L)
    request = features_pb2.ListHotlistsByUserRequest(user=user_ref)

    # We're authenticated as 'foo@example.com'
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.com')
    response = self.CallWrapped(self.features_svcr.ListHotlistsByUser, mc,
                                request)

    self.assertEqual(0, len(response.hotlists))

  def testListHotlistsByUser_PrivateIssueNotSignedIn(self):
    # Private hostlist owned by 'owner@example.com'
    self.services.features.CreateHotlist(
        self.cnxn, 'Fake Hotlist', 'Summary', 'Description',
        owner_ids=[111L], editor_ids=[222L], is_private=True)

    # Query for issues for 'owner@example.com'
    user_ref = common_pb2.UserRef(user_id=111L)
    request = features_pb2.ListHotlistsByUserRequest(user=user_ref)

    # We're not authenticated
    mc = monorailcontext.MonorailContext(self.services, cnxn=self.cnxn)
    response = self.CallWrapped(self.features_svcr.ListHotlistsByUser, mc,
                                request)

    self.assertEqual(0, len(response.hotlists))

  def CallGetStarCount(self):
    # Query for hotlists for 'owner@example.com'
    owner_ref = common_pb2.UserRef(user_id=111L)
    hotlist_ref = common_pb2.HotlistRef(name='Fake Hotlist', owner=owner_ref)
    request = features_pb2.GetHotlistStarCountRequest(hotlist_ref=hotlist_ref)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.features_svcr.GetHotlistStarCount, mc, request)
    return response.star_count

  def CallStar(self, requester='owner@example.com', starred=True):
    # Query for hotlists for 'owner@example.com'
    owner_ref = common_pb2.UserRef(user_id=111L)
    hotlist_ref = common_pb2.HotlistRef(name='Fake Hotlist', owner=owner_ref)
    request = features_pb2.StarHotlistRequest(
        hotlist_ref=hotlist_ref, starred=starred)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester=requester)
    response = self.CallWrapped(
        self.features_svcr.StarHotlist, mc, request)
    return response.star_count

  def testStarCount_Normal(self):
    self.services.features.CreateHotlist(
        self.cnxn, 'Fake Hotlist', 'Summary', 'Description',
        owner_ids=[111L], editor_ids=[222L])
    self.assertEqual(0, self.CallGetStarCount())
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallGetStarCount())

  def testStarCount_StarTwiceSameUser(self):
    self.services.features.CreateHotlist(
        self.cnxn, 'Fake Hotlist', 'Summary', 'Description',
        owner_ids=[111L], editor_ids=[222L])
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallGetStarCount())

  def testStarCount_StarTwiceDifferentUser(self):
    self.services.features.CreateHotlist(
        self.cnxn, 'Fake Hotlist', 'Summary', 'Description',
        owner_ids=[111L], editor_ids=[222L])
    self.assertEqual(1, self.CallStar())
    self.assertEqual(2, self.CallStar(requester='user_222@example.com'))
    self.assertEqual(2, self.CallGetStarCount())

  def testStarCount_RemoveStarTwiceSameUser(self):
    self.services.features.CreateHotlist(
        self.cnxn, 'Fake Hotlist', 'Summary', 'Description',
        owner_ids=[111L], editor_ids=[222L])
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallGetStarCount())

    self.assertEqual(0, self.CallStar(starred=False))
    self.assertEqual(0, self.CallStar(starred=False))
    self.assertEqual(0, self.CallGetStarCount())

  def testStarCount_RemoveStarTwiceDifferentUser(self):
    self.services.features.CreateHotlist(
        self.cnxn, 'Fake Hotlist', 'Summary', 'Description',
        owner_ids=[111L], editor_ids=[222L])
    self.assertEqual(1, self.CallStar())
    self.assertEqual(2, self.CallStar(requester='user_222@example.com'))
    self.assertEqual(2, self.CallGetStarCount())

    self.assertEqual(1, self.CallStar(starred=False))
    self.assertEqual(
        0, self.CallStar(requester='user_222@example.com', starred=False))
    self.assertEqual(0, self.CallGetStarCount())

  def testListHotlistIssues(self):
    hotlist_id = self.services.features.CreateHotlist(
        self.cnxn, 'Fake Hotlist', 'Summary', 'Description',
        owner_ids=[111L], editor_ids=[]).hotlist_id
    self.services.features.UpdateHotlistItems(
        self.cnxn, hotlist_id, [],
        [(self.issue_1.issue_id, 222L, 12345, 'Note'),
         (self.issue_2.issue_id, 111L, 12346, 'Note')])
    self.issue_2.labels = ['Restrict-View-CoreTeam']

    owner_ref = common_pb2.UserRef(user_id=111L)
    hotlist_ref = common_pb2.HotlistRef(name='Fake Hotlist', owner=owner_ref)
    request = features_pb2.ListHotlistIssuesRequest(hotlist_ref=hotlist_ref)

    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.features_svcr.ListHotlistIssues, mc, request)

    self.assertEqual(1, len(response.items))
    self.assertEqual(10, response.items[0].rank)
    self.assertEqual(12345, response.items[0].added_timestamp)
    self.assertEqual('Note', response.items[0].note)
    self.assertEqual(
        common_pb2.UserRef(
            user_id=222L,
            display_name='edi...@example.com'),
        response.items[0].adder_ref)
    self.assertEqual(1, response.items[0].issue.local_id)
    self.assertEqual('proj', response.items[0].issue.project_name)
    self.assertEqual('sum', response.items[0].issue.summary)
    self.assertEqual('New', response.items[0].issue.status_ref.status)

  def testDismissCue(self):
    user = self.services.user.test_users[111L]
    self.assertEqual(0, len(user.dismissed_cues))

    request = features_pb2.DismissCueRequest(cue_id='code_of_conduct')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(self.features_svcr.DismissCue, mc, request)

    self.assertEqual(['code_of_conduct'], user.dismissed_cues)
