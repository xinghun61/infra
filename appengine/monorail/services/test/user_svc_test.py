# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the user service."""

import unittest

import mox
import time

from google.appengine.ext import testbed

from framework import sql
from proto import user_pb2
from services import user_svc
from testing import fake


def SetUpGetUsers(user_service, cnxn):
  """Set up expected calls to SQL tables."""
  user_service.user_tbl.Select(
      cnxn, cols=user_svc.USER_COLS, user_id=[333L]).AndReturn(
          [(333L, 'c@example.com', False, False, False, False, True,
            False, 'Spammer',
            'stay_same_issue', False, False, False, True, 0, 0, None)])
  user_service.actionlimit_tbl.Select(
      cnxn, cols=user_svc.ACTIONLIMIT_COLS, user_id=[333L]).AndReturn([])
  user_service.dismissedcues_tbl.Select(
      cnxn, cols=user_svc.DISMISSEDCUES_COLS, user_id=[333L]).AndReturn([])


def MakeUserService(cache_manager, my_mox):
  user_service = user_svc.UserService(cache_manager)
  user_service.user_tbl = my_mox.CreateMock(sql.SQLTableManager)
  user_service.actionlimit_tbl = my_mox.CreateMock(sql.SQLTableManager)
  user_service.dismissedcues_tbl = my_mox.CreateMock(sql.SQLTableManager)
  user_service.hotlistvisithistory_tbl = my_mox.CreateMock(sql.SQLTableManager)
  user_service.linkedaccount_tbl = my_mox.CreateMock(sql.SQLTableManager)
  return user_service


class UserTwoLevelCacheTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.mox = mox.Mox()
    self.cnxn = fake.MonorailConnection()
    self.cache_manager = fake.CacheManager()
    self.user_service = MakeUserService(self.cache_manager, self.mox)

  def tearDown(self):
    self.testbed.deactivate()

  def testDeserializeUsersByID(self):
    user_rows = [
        (111L, 'a@example.com', False, False, False, False, True, False, '',
         'stay_same_issue', False, False, False, True, 0, 0, None),
        (222L, 'b@example.com', False, False, False, False, True, False, '',
         'next_in_list', False, False, False, True, 0, 0, None),
        ]
    actionlimit_rows = []
    dismissedcues_rows = []
    user_dict = self.user_service.user_2lc._DeserializeUsersByID(
        user_rows, actionlimit_rows, dismissedcues_rows)
    self.assertEqual(2, len(user_dict))
    self.assertEqual('a@example.com', user_dict[111L].email)
    self.assertFalse(user_dict[111L].is_site_admin)
    self.assertEqual('', user_dict[111L].banned)
    self.assertFalse(user_dict[111L].notify_issue_change)
    self.assertEqual('b@example.com', user_dict[222L].email)

  def testFetchItems(self):
    SetUpGetUsers(self.user_service, self.cnxn)
    self.mox.ReplayAll()
    user_dict = self.user_service.user_2lc.FetchItems(self.cnxn, [333L])
    self.mox.VerifyAll()
    self.assertEqual([333L], user_dict.keys())
    self.assertEqual('c@example.com', user_dict[333L].email)
    self.assertFalse(user_dict[333L].is_site_admin)
    self.assertEqual('Spammer', user_dict[333L].banned)


class UserServiceTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.mox = mox.Mox()
    self.cnxn = fake.MonorailConnection()
    self.cache_manager = fake.CacheManager()
    self.user_service = MakeUserService(self.cache_manager, self.mox)

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def SetUpCreateUsers(self):
    self.user_service.user_tbl.InsertRows(
        self.cnxn,
        ['user_id', 'email', 'obscure_email'],
        [(3035911623, 'a@example.com', True),
         (2996997680, 'b@example.com', True)]
    ).AndReturn(None)

  def testCreateUsers(self):
    self.SetUpCreateUsers()
    self.mox.ReplayAll()
    self.user_service._CreateUsers(
        self.cnxn, ['a@example.com', 'b@example.com'])
    self.mox.VerifyAll()

  def SetUpLookupUserEmails(self):
    self.user_service.user_tbl.Select(
        self.cnxn, cols=['user_id', 'email'], user_id=[222L]).AndReturn(
            [(222L, 'b@example.com')])

  def testLookupUserEmails(self):
    self.SetUpLookupUserEmails()
    self.user_service.email_cache.CacheItem(
        111L, 'a@example.com')
    self.mox.ReplayAll()
    emails_dict = self.user_service.LookupUserEmails(
        self.cnxn, [111L, 222L])
    self.mox.VerifyAll()
    self.assertEqual(
        {111L: 'a@example.com', 222L: 'b@example.com'},
        emails_dict)

  def testLookupUserEmail(self):
    self.SetUpLookupUserEmails()  # Same as testLookupUserEmails()
    self.mox.ReplayAll()
    email_addr = self.user_service.LookupUserEmail(self.cnxn, 222L)
    self.mox.VerifyAll()
    self.assertEqual('b@example.com', email_addr)

  def SetUpLookupUserIDs(self):
    self.user_service.user_tbl.Select(
        self.cnxn, cols=['email', 'user_id'],
        email=['b@example.com']).AndReturn([('b@example.com', 222L)])

  def testLookupUserIDs(self):
    self.SetUpLookupUserIDs()
    self.user_service.user_id_cache.CacheItem(
        'a@example.com', 111L)
    self.mox.ReplayAll()
    user_id_dict = self.user_service.LookupUserIDs(
        self.cnxn, ['a@example.com', 'b@example.com'])
    self.mox.VerifyAll()
    self.assertEqual(
        {'a@example.com': 111L, 'b@example.com': 222L},
        user_id_dict)

  def testLookupUserIDs_InvalidEmail(self):
    self.user_service.user_tbl.Select(
        self.cnxn, cols=['email', 'user_id'], email=['abc']).AndReturn([])
    self.mox.ReplayAll()
    user_id_dict = self.user_service.LookupUserIDs(
        self.cnxn, ['abc'], autocreate=True)
    self.mox.VerifyAll()
    self.assertEqual({}, user_id_dict)

  def testLookupUserID(self):
    self.SetUpLookupUserIDs()  # Same as testLookupUserIDs()
    self.user_service.user_id_cache.CacheItem('a@example.com', 111L)
    self.mox.ReplayAll()
    user_id = self.user_service.LookupUserID(self.cnxn, 'b@example.com')
    self.mox.VerifyAll()
    self.assertEqual(222, user_id)

  def testGetUsersByIDs(self):
    SetUpGetUsers(self.user_service, self.cnxn)
    user_a = user_pb2.User(email='a@example.com')
    self.user_service.user_2lc.CacheItem(111L, user_a)
    self.mox.ReplayAll()
    user_dict = self.user_service.GetUsersByIDs(
        self.cnxn, [111L, 333L])
    self.mox.VerifyAll()
    self.assertEqual(2, len(user_dict))
    self.assertEqual('a@example.com', user_dict[111L].email)
    self.assertFalse(user_dict[111L].is_site_admin)
    self.assertFalse(user_dict[111L].banned)
    self.assertTrue(user_dict[111L].notify_issue_change)
    self.assertEqual('c@example.com', user_dict[333L].email)

  def testGetUser(self):
    SetUpGetUsers(self.user_service, self.cnxn)
    user_a = user_pb2.User(email='a@example.com')
    self.user_service.user_2lc.CacheItem(111L, user_a)
    self.mox.ReplayAll()
    user = self.user_service.GetUser(self.cnxn, 333L)
    self.mox.VerifyAll()
    self.assertEqual('c@example.com', user.email)

  def SetUpUpdateUser(self):
    delta = {
        'keep_people_perms_open': False,
        'preview_on_hover': True,
        'ignore_action_limits': False,
        'notify_issue_change': True,
        'after_issue_update': 'STAY_SAME_ISSUE',
        'notify_starred_issue_change': True,
        'notify_starred_ping': False,
        'is_site_admin': False,
        'banned': 'Turned spammer',
        'obscure_email': True,
        'email_compact_subject': False,
        'email_view_widget': True,
        'last_visit_timestamp': 0,
        'email_bounce_timestamp': 0,
        'vacation_message': None,
    }
    self.user_service.user_tbl.Update(
        self.cnxn, delta, user_id=111L, commit=False)

    self.user_service.actionlimit_tbl.Delete(
        self.cnxn, user_id=111L, commit=False)
    self.user_service.actionlimit_tbl.InsertRows(
        self.cnxn, user_svc.ACTIONLIMIT_COLS, [], commit=False)

    self.user_service.dismissedcues_tbl.Delete(
        self.cnxn, user_id=111L, commit=False)
    self.user_service.dismissedcues_tbl.InsertRows(
        self.cnxn, user_svc.DISMISSEDCUES_COLS, [], commit=False)

  def testUpdateUser(self):
    self.SetUpUpdateUser()
    user_a = user_pb2.User(
        email='a@example.com', banned='Turned spammer')
    self.mox.ReplayAll()
    self.user_service.UpdateUser(self.cnxn, 111L, user_a)
    self.mox.VerifyAll()
    self.assertFalse(self.user_service.user_2lc.HasItem(111L))

  def SetUpGetRecentlyVisitedHotlists(self):
    self.user_service.hotlistvisithistory_tbl.Select(
        self.cnxn, cols=['hotlist_id'], user_id=[111L],
        order_by=[('viewed DESC', [])], limit=10).AndReturn(
            ((123,), (234,)))

  def testGetRecentlyVisitedHotlists(self):
    self.SetUpGetRecentlyVisitedHotlists()
    self.mox.ReplayAll()
    recent_hotlist_rows = self.user_service.GetRecentlyVisitedHotlists(
        self.cnxn, 111L)
    self.mox.VerifyAll()
    self.assertEqual(recent_hotlist_rows, [123, 234])

  def SetUpAddVisitedHotlist(self):
    self.user_service.hotlistvisithistory_tbl.Delete(
        self.cnxn, hotlist_id=123, user_id=111L, commit=False)
    self.user_service.hotlistvisithistory_tbl.InsertRows(
        self.cnxn, user_svc.HOTLISTVISITHISTORY_COLS,
        [(123, 111L, int(time.time()))],
        commit=False)

  def testAddVisitedHotlist(self):
    self.SetUpAddVisitedHotlist()
    self.mox.ReplayAll()
    self.user_service.AddVisitedHotlist(self.cnxn, 111L, 123, commit=False)
    self.mox.VerifyAll()

  def SetUpTrimUserVisitedHotlists(self, user_ids):
    self.user_service.hotlistvisithistory_tbl.Select(
        self.cnxn, cols=['user_id'], group_by=['user_id'],
        having=[('COUNT(*) > %s', [10])], limit=1000).AndReturn((
            (111L,), (222L,), (333L,)))
    ts = int(time.time())
    for user_id in user_ids:
      self.user_service.hotlistvisithistory_tbl.Select(
          self.cnxn, cols=['viewed'], user_id=user_id,
          order_by=[('viewed DESC', [])]).AndReturn([
              (ts,), (ts,), (ts,), (ts,), (ts,), (ts,),
              (ts,), (ts,), (ts,), (ts,), (ts+1,)])
      self.user_service.hotlistvisithistory_tbl.Delete(
          self.cnxn, user_id=user_id, where=[('viewed < %s', [ts])],
          commit=False)

  def testTrimUserVisitedHotlists(self):
    self.SetUpTrimUserVisitedHotlists([111L, 222L, 333L])
    self.mox.ReplayAll()
    self.user_service.TrimUserVisitedHotlists(self.cnxn, commit=False)
    self.mox.VerifyAll()

  def SetUpLookupParentEmail(self):
    self.user_service.linkedaccount_tbl.SelectValue(
        self.cnxn, 'parent_email', child_email='test@google.com').AndReturn(
            'test@chromium.org')

  def testLookupParentEmail(self):
    self.SetUpLookupParentEmail()
    self.mox.ReplayAll()
    parent_email = self.user_service.LookupParentEmail(self.cnxn,
        'test@google.com')
    self.mox.VerifyAll()
    self.assertEqual('test@chromium.org', parent_email)

  def testUpdateUserSettings(self):
    self.SetUpUpdateUser()
    user_a = user_pb2.User(email='a@example.com')
    self.mox.ReplayAll()
    self.user_service.UpdateUserSettings(
        self.cnxn, 111L, user_a, is_banned=True,
        banned_reason='Turned spammer')
    self.mox.VerifyAll()


class UserServiceFunctionsTest(unittest.TestCase):

  def testActionLimitToRow(self):
    al = user_pb2.ActionLimit(
        recent_count=1, reset_timestamp=123456, lifetime_count=9,
        lifetime_limit=10, period_soft_limit=2, period_hard_limit=5)
    action_kind = 3
    row = user_svc._ActionLimitToRow(
        111, action_kind, al)
    self.assertEqual((111, action_kind, 1, 123456, 9, 10, 2, 5), row)
