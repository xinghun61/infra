# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the user service."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

import mock
import mox
import time

from google.appengine.ext import testbed

from framework import exceptions
from framework import framework_constants
from framework import sql
from proto import user_pb2
from services import user_svc
from testing import fake


def SetUpGetUsers(user_service, cnxn):
  """Set up expected calls to SQL tables."""
  user_service.user_tbl.Select(
      cnxn, cols=user_svc.USER_COLS, user_id=[333]).AndReturn(
          [(333, 'c@example.com', False, False, False, False, True,
            False, 'Spammer',
            'stay_same_issue', False, False, True, 0, 0, None)])
  user_service.dismissedcues_tbl.Select(
      cnxn, cols=user_svc.DISMISSEDCUES_COLS, user_id=[333]).AndReturn([])
  user_service.linkedaccount_tbl.Select(
      cnxn, cols=user_svc.LINKEDACCOUNT_COLS, parent_id=[333], child_id=[333],
      or_where_conds=True).AndReturn([])


def MakeUserService(cache_manager, my_mox):
  user_service = user_svc.UserService(cache_manager)
  user_service.user_tbl = my_mox.CreateMock(sql.SQLTableManager)
  user_service.dismissedcues_tbl = my_mox.CreateMock(sql.SQLTableManager)
  user_service.hotlistvisithistory_tbl = my_mox.CreateMock(sql.SQLTableManager)
  user_service.linkedaccount_tbl = my_mox.CreateMock(sql.SQLTableManager)
  # Account linking invites are done with patch().
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
        (111, 'a@example.com', False, False, False, False, True, False, '',
         'stay_same_issue', False, False, True, 0, 0, None),
        (222, 'b@example.com', False, False, False, False, True, False, '',
         'next_in_list', False, False, True, 0, 0, None),
        ]
    dismissedcues_rows = []
    linkedaccount_rows = []
    user_dict = self.user_service.user_2lc._DeserializeUsersByID(
        user_rows, dismissedcues_rows, linkedaccount_rows)
    self.assertEqual(2, len(user_dict))
    self.assertEqual('a@example.com', user_dict[111].email)
    self.assertFalse(user_dict[111].is_site_admin)
    self.assertEqual('', user_dict[111].banned)
    self.assertFalse(user_dict[111].notify_issue_change)
    self.assertEqual('b@example.com', user_dict[222].email)
    self.assertIsNone(user_dict[111].linked_parent_id)
    self.assertEqual([], user_dict[111].linked_child_ids)
    self.assertIsNone(user_dict[222].linked_parent_id)
    self.assertEqual([], user_dict[222].linked_child_ids)

  def testDeserializeUsersByID_LinkedAccounts(self):
    user_rows = [
        (111, 'a@example.com', False, False, False, False, True, False, '',
         'stay_same_issue', False, False, True, 0, 0, None),
        ]
    dismissedcues_rows = []
    linkedaccount_rows = [(111, 222), (111, 333), (444, 111)]
    user_dict = self.user_service.user_2lc._DeserializeUsersByID(
        user_rows, dismissedcues_rows, linkedaccount_rows)
    self.assertEqual(1, len(user_dict))
    user_pb = user_dict[111]
    self.assertEqual('a@example.com', user_pb.email)
    self.assertEqual(444, user_pb.linked_parent_id)
    self.assertEqual([222, 333], user_pb.linked_child_ids)

  def testFetchItems(self):
    SetUpGetUsers(self.user_service, self.cnxn)
    self.mox.ReplayAll()
    user_dict = self.user_service.user_2lc.FetchItems(self.cnxn, [333])
    self.mox.VerifyAll()
    self.assertEqual([333], list(user_dict.keys()))
    self.assertEqual('c@example.com', user_dict[333].email)
    self.assertFalse(user_dict[333].is_site_admin)
    self.assertEqual('Spammer', user_dict[333].banned)


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
        self.cnxn, cols=['user_id', 'email'], user_id=[222]).AndReturn(
            [(222, 'b@example.com')])

  def testLookupUserEmails(self):
    self.SetUpLookupUserEmails()
    self.user_service.email_cache.CacheItem(
        111, 'a@example.com')
    self.mox.ReplayAll()
    emails_dict = self.user_service.LookupUserEmails(
        self.cnxn, [111, 222])
    self.mox.VerifyAll()
    self.assertEqual(
        {111: 'a@example.com', 222: 'b@example.com'},
        emails_dict)

  def SetUpLookupUserEmails_Missed(self):
    self.user_service.user_tbl.Select(
        self.cnxn, cols=['user_id', 'email'], user_id=[222]).AndReturn([])
    self.user_service.email_cache.CacheItem(
        111, 'a@example.com')

  def testLookupUserEmails_Missed(self):
    self.SetUpLookupUserEmails_Missed()
    self.mox.ReplayAll()
    with self.assertRaises(exceptions.NoSuchUserException):
      self.user_service.LookupUserEmails(self.cnxn, [111, 222])
    self.mox.VerifyAll()

  def testLookUpUserEmails_IgnoreMissed(self):
    self.SetUpLookupUserEmails_Missed()
    self.mox.ReplayAll()
    emails_dict = self.user_service.LookupUserEmails(
        self.cnxn, [111, 222], ignore_missed=True)
    self.mox.VerifyAll()
    self.assertEqual({111: 'a@example.com'}, emails_dict)

  def testLookupUserEmail(self):
    self.SetUpLookupUserEmails()  # Same as testLookupUserEmails()
    self.mox.ReplayAll()
    email_addr = self.user_service.LookupUserEmail(self.cnxn, 222)
    self.mox.VerifyAll()
    self.assertEqual('b@example.com', email_addr)

  def SetUpLookupUserIDs(self):
    self.user_service.user_tbl.Select(
        self.cnxn, cols=['email', 'user_id'],
        email=['b@example.com']).AndReturn([('b@example.com', 222)])

  def testLookupUserIDs(self):
    self.SetUpLookupUserIDs()
    self.user_service.user_id_cache.CacheItem(
        'a@example.com', 111)
    self.mox.ReplayAll()
    user_id_dict = self.user_service.LookupUserIDs(
        self.cnxn, ['a@example.com', 'b@example.com'])
    self.mox.VerifyAll()
    self.assertEqual(
        {'a@example.com': 111, 'b@example.com': 222},
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
    self.user_service.user_id_cache.CacheItem('a@example.com', 111)
    self.mox.ReplayAll()
    user_id = self.user_service.LookupUserID(self.cnxn, 'b@example.com')
    self.mox.VerifyAll()
    self.assertEqual(222, user_id)

  def testGetUsersByIDs(self):
    SetUpGetUsers(self.user_service, self.cnxn)
    user_a = user_pb2.User(email='a@example.com')
    self.user_service.user_2lc.CacheItem(111, user_a)
    self.mox.ReplayAll()
    user_dict = self.user_service.GetUsersByIDs(
        self.cnxn, [111, 333])
    self.mox.VerifyAll()
    self.assertEqual(2, len(user_dict))
    self.assertEqual('a@example.com', user_dict[111].email)
    self.assertFalse(user_dict[111].is_site_admin)
    self.assertFalse(user_dict[111].banned)
    self.assertTrue(user_dict[111].notify_issue_change)
    self.assertEqual('c@example.com', user_dict[333].email)

  def testGetUser(self):
    SetUpGetUsers(self.user_service, self.cnxn)
    user_a = user_pb2.User(email='a@example.com')
    self.user_service.user_2lc.CacheItem(111, user_a)
    self.mox.ReplayAll()
    user = self.user_service.GetUser(self.cnxn, 333)
    self.mox.VerifyAll()
    self.assertEqual('c@example.com', user.email)

  def SetUpUpdateUser(self):
    delta = {
        'keep_people_perms_open': False,
        'preview_on_hover': True,
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
        self.cnxn, delta, user_id=111, commit=False)

    self.user_service.dismissedcues_tbl.Delete(
        self.cnxn, user_id=111, commit=False)
    self.user_service.dismissedcues_tbl.InsertRows(
        self.cnxn, user_svc.DISMISSEDCUES_COLS, [], commit=False)

  def testUpdateUser(self):
    self.SetUpUpdateUser()
    user_a = user_pb2.User(
        email='a@example.com', banned='Turned spammer')
    self.mox.ReplayAll()
    self.user_service.UpdateUser(self.cnxn, 111, user_a)
    self.mox.VerifyAll()
    self.assertFalse(self.user_service.user_2lc.HasItem(111))

  def SetUpGetRecentlyVisitedHotlists(self):
    self.user_service.hotlistvisithistory_tbl.Select(
        self.cnxn, cols=['hotlist_id'], user_id=[111],
        order_by=[('viewed DESC', [])], limit=10).AndReturn(
            ((123,), (234,)))

  def testGetRecentlyVisitedHotlists(self):
    self.SetUpGetRecentlyVisitedHotlists()
    self.mox.ReplayAll()
    recent_hotlist_rows = self.user_service.GetRecentlyVisitedHotlists(
        self.cnxn, 111)
    self.mox.VerifyAll()
    self.assertEqual(recent_hotlist_rows, [123, 234])

  def SetUpAddVisitedHotlist(self):
    self.user_service.hotlistvisithistory_tbl.Delete(
        self.cnxn, hotlist_id=123, user_id=111, commit=False)
    self.user_service.hotlistvisithistory_tbl.InsertRows(
        self.cnxn, user_svc.HOTLISTVISITHISTORY_COLS,
        [(123, 111, int(time.time()))],
        commit=False)

  def testAddVisitedHotlist(self):
    self.SetUpAddVisitedHotlist()
    self.mox.ReplayAll()
    self.user_service.AddVisitedHotlist(self.cnxn, 111, 123, commit=False)
    self.mox.VerifyAll()

  def testExpungeHotlistsFromHistory(self):
    self.user_service.hotlistvisithistory_tbl.Delete = mock.Mock()
    hotlist_ids = [123, 223]
    self.user_service.ExpungeHotlistsFromHistory(
        self.cnxn, hotlist_ids, commit=False)
    self.user_service.hotlistvisithistory_tbl.Delete.assert_called_once_with(
        self.cnxn, hotlist_id=hotlist_ids, commit=False)

  def testExpungeUsersHotlistsHistory(self):
    self.user_service.hotlistvisithistory_tbl.Delete = mock.Mock()
    user_ids = [111, 222]
    self.user_service.ExpungeUsersHotlistsHistory(
        self.cnxn, user_ids, commit=False)
    self.user_service.hotlistvisithistory_tbl.Delete.assert_called_once_with(
        self.cnxn, user_id=user_ids, commit=False)

  def SetUpTrimUserVisitedHotlists(self, user_ids):
    self.user_service.hotlistvisithistory_tbl.Select(
        self.cnxn, cols=['user_id'], group_by=['user_id'],
        having=[('COUNT(*) > %s', [10])], limit=1000).AndReturn((
            (111,), (222,), (333,)))
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
    self.SetUpTrimUserVisitedHotlists([111, 222, 333])
    self.mox.ReplayAll()
    self.user_service.TrimUserVisitedHotlists(self.cnxn, commit=False)
    self.mox.VerifyAll()

  def testGetPendingLinkedInvites_Anon(self):
    """An Anon user never has invites to link accounts."""
    as_parent, as_child = self.user_service.GetPendingLinkedInvites(
        self.cnxn, 0)
    self.assertEqual([], as_parent)
    self.assertEqual([], as_child)

  def testGetPendingLinkedInvites_None(self):
    """A user who has no link invites gets empty lists."""
    self.user_service.linkedaccountinvite_tbl = mock.Mock()
    self.user_service.linkedaccountinvite_tbl.Select.return_value = []
    as_parent, as_child = self.user_service.GetPendingLinkedInvites(
        self.cnxn, 111)
    self.assertEqual([], as_parent)
    self.assertEqual([], as_child)

  def testGetPendingLinkedInvites_Some(self):
    """A user who has link invites can get them."""
    self.user_service.linkedaccountinvite_tbl = mock.Mock()
    self.user_service.linkedaccountinvite_tbl.Select.return_value = [
        (111, 222), (111, 333), (888, 999), (333, 111)]
    as_parent, as_child = self.user_service.GetPendingLinkedInvites(
        self.cnxn, 111)
    self.assertEqual([222, 333], as_parent)
    self.assertEqual([333], as_child)

  def testAssertNotAlreadyLinked_NotLinked(self):
    """No exception is raised when accounts are not already linked."""
    self.user_service.linkedaccount_tbl = mock.Mock()
    self.user_service.linkedaccount_tbl.Select.return_value = []
    self.user_service._AssertNotAlreadyLinked(self.cnxn, 111, 222)

  def testAssertNotAlreadyLinked_AlreadyLinked(self):
    """Reject attempt to link any account that is already linked."""
    self.user_service.linkedaccount_tbl = mock.Mock()
    self.user_service.linkedaccount_tbl.Select.return_value = [
        (111, 222)]
    with self.assertRaises(exceptions.InputException):
      self.user_service._AssertNotAlreadyLinked(self.cnxn, 111, 333)

  def testInviteLinkedParent_Anon(self):
    """Anon cannot invite anyone to link accounts."""
    with self.assertRaises(exceptions.InputException):
      self.user_service.InviteLinkedParent(self.cnxn, 0, 0)
    with self.assertRaises(exceptions.InputException):
      self.user_service.InviteLinkedParent(self.cnxn, 111, 0)
    with self.assertRaises(exceptions.InputException):
      self.user_service.InviteLinkedParent(self.cnxn, 0, 111)

  def testInviteLinkedParent_Normal(self):
    """One account can invite another to link."""
    self.user_service.linkedaccount_tbl = mock.Mock()
    self.user_service.linkedaccount_tbl.Select.return_value = []
    self.user_service.linkedaccountinvite_tbl = mock.Mock()
    self.user_service.InviteLinkedParent(
        self.cnxn, 111, 222)
    self.user_service.linkedaccountinvite_tbl.InsertRow.assert_called_once_with(
        self.cnxn, parent_id=111, child_id=222)

  def testAcceptLinkedChild_Anon(self):
    """Reject attempts for anon to accept any invite."""
    with self.assertRaises(exceptions.InputException):
      self.user_service.AcceptLinkedChild(self.cnxn, 0, 333)
    with self.assertRaises(exceptions.InputException):
      self.user_service.AcceptLinkedChild(self.cnxn, 333, 0)

  def testAcceptLinkedChild_Missing(self):
    """Reject attempts to link without a matching invite."""
    self.user_service.linkedaccountinvite_tbl = mock.Mock()
    self.user_service.linkedaccountinvite_tbl.Select.return_value = []
    self.user_service.linkedaccount_tbl = mock.Mock()
    self.user_service.linkedaccount_tbl.Select.return_value = []
    with self.assertRaises(exceptions.InputException) as cm:
      self.user_service.AcceptLinkedChild(self.cnxn, 111, 333)
    self.assertEqual('No such invite', cm.exception.message)

  def testAcceptLinkedChild_Normal(self):
    """Create linkage between accounts and remove invite."""
    self.user_service.linkedaccountinvite_tbl = mock.Mock()
    self.user_service.linkedaccountinvite_tbl.Select.return_value = [
        (111, 222), (333, 444)]
    self.user_service.linkedaccount_tbl = mock.Mock()
    self.user_service.linkedaccount_tbl.Select.return_value = []

    self.user_service.AcceptLinkedChild(self.cnxn, 111, 222)
    self.user_service.linkedaccount_tbl.InsertRow.assert_called_once_with(
        self.cnxn, parent_id=111, child_id=222)
    self.user_service.linkedaccountinvite_tbl.Delete.assert_called_once_with(
        self.cnxn, parent_id=111, child_id=222)

  def testUnlinkAccounts_MissingIDs(self):
    """Reject an attempt to unlink anon."""
    with self.assertRaises(exceptions.InputException):
      self.user_service.UnlinkAccounts(self.cnxn, 0, 0)
    with self.assertRaises(exceptions.InputException):
      self.user_service.UnlinkAccounts(self.cnxn, 0, 111)
    with self.assertRaises(exceptions.InputException):
      self.user_service.UnlinkAccounts(self.cnxn, 111, 0)

  def testUnlinkAccounts_Normal(self):
    """We can unlink accounts."""
    self.user_service.linkedaccount_tbl = mock.Mock()
    self.user_service.UnlinkAccounts(self.cnxn, 111, 222)
    self.user_service.linkedaccount_tbl.Delete.assert_called_once_with(
        self.cnxn, parent_id=111, child_id=222)

  def testUpdateUserSettings(self):
    self.SetUpUpdateUser()
    user_a = user_pb2.User(email='a@example.com')
    self.mox.ReplayAll()
    self.user_service.UpdateUserSettings(
        self.cnxn, 111, user_a, is_banned=True,
        banned_reason='Turned spammer')
    self.mox.VerifyAll()

  def testGetUsersPrefs(self):
    self.user_service.userprefs_tbl = mock.Mock()
    self.user_service.userprefs_tbl.Select.return_value = [
        (111, 'code_font', 'true'),
        (111, 'keep_perms_open', 'true'),
        # Note: user 222 has not set any prefs.
        (333, 'code_font', 'false')]

    prefs_dict = self.user_service.GetUsersPrefs(self.cnxn, [111, 222, 333])

    expected = {
      111: user_pb2.UserPrefs(
          user_id=111,
          prefs=[user_pb2.UserPrefValue(name='code_font', value='true'),
                 user_pb2.UserPrefValue(name='keep_perms_open', value='true')]),
      222: user_pb2.UserPrefs(user_id=222),
      333: user_pb2.UserPrefs(
          user_id=333,
          prefs=[user_pb2.UserPrefValue(name='code_font', value='false')]),
      }
    self.assertEqual(expected, prefs_dict)

  def testGetUserPrefs(self):
    self.user_service.userprefs_tbl = mock.Mock()
    self.user_service.userprefs_tbl.Select.return_value = [
        (111, 'code_font', 'true'),
        (111, 'keep_perms_open', 'true'),
        # Note: user 222 has not set any prefs.
        (333, 'code_font', 'false')]

    userprefs = self.user_service.GetUserPrefs(self.cnxn, 111)
    expected = user_pb2.UserPrefs(
        user_id=111,
        prefs=[user_pb2.UserPrefValue(name='code_font', value='true'),
               user_pb2.UserPrefValue(name='keep_perms_open', value='true')])
    self.assertEqual(expected, userprefs)

    userprefs = self.user_service.GetUserPrefs(self.cnxn, 222)
    expected = user_pb2.UserPrefs(user_id=222)
    self.assertEqual(expected, userprefs)

  def testSetUserPrefs(self):
    self.user_service.userprefs_tbl = mock.Mock()
    pref_values = [user_pb2.UserPrefValue(name='code_font', value='true'),
                   user_pb2.UserPrefValue(name='keep_perms_open', value='true')]
    self.user_service.SetUserPrefs(self.cnxn, 111, pref_values)
    self.user_service.userprefs_tbl.InsertRows.assert_called_once_with(
        self.cnxn, user_svc.USERPREFS_COLS,
        [(111, 'code_font', 'true'),
         (111, 'keep_perms_open', 'true')],
        replace=True)

  def testExpungeUsers(self):
    self.user_service.linkedaccount_tbl.Delete = mock.Mock()
    self.user_service.linkedaccountinvite_tbl.Delete = mock.Mock()
    self.user_service.dismissedcues_tbl.Delete = mock.Mock()
    self.user_service.userprefs_tbl.Delete = mock.Mock()
    self.user_service.user_tbl.Delete = mock.Mock()

    user_ids = [222, 444]
    self.user_service.ExpungeUsers(self.cnxn, user_ids)

    linked_account_calls = [
        mock.call(self.cnxn, parent_id=user_ids, commit=False),
        mock.call(self.cnxn, child_id=user_ids, commit=False)]
    self.user_service.linkedaccount_tbl.Delete.has_calls(linked_account_calls)
    self.user_service.linkedaccountinvite_tbl.Delete.has_calls(
        linked_account_calls)
    user_calls = [mock.call(self.cnxn, user_id=user_ids, commit=False)]
    self.user_service.dismissedcues_tbl.Delete.has_calls(user_calls)
    self.user_service.userprefs_tbl.Delete.has_calls(user_calls)
    self.user_service.user_tbl.Delete.has_calls(user_calls)

  def testTotalUsersCount(self):
    self.user_service.user_tbl.SelectValue = mock.Mock(return_value=10)
    self.assertEqual(self.user_service.TotalUsersCount(self.cnxn), 9)
    self.user_service.user_tbl.SelectValue.assert_called_once_with(
        self.cnxn, col='COUNT(*)')

  def testGetAllUserEmailsBatch(self):
    rows = [('cow@test.com',), ('pig@test.com',), ('fox@test.com',)]
    self.user_service.user_tbl.Select = mock.Mock(return_value=rows)
    emails = self.user_service.GetAllUserEmailsBatch(self.cnxn)
    self.user_service.user_tbl.Select.assert_called_once_with(
        self.cnxn, cols=['email'], limit=1000, offset=0,
        where=[('user_id != %s', [framework_constants.DELETED_USER_ID])],
        order_by=[('user_id ASC'), []])
    self.assertItemsEqual(
        emails, ['cow@test.com', 'pig@test.com', 'fox@test.com'])

  def testGetAllUserEmailsBatch_CustomLimit(self):
    rows = [('cow@test.com',), ('pig@test.com',), ('fox@test.com',)]
    self.user_service.user_tbl.Select = mock.Mock(return_value=rows)
    emails = self.user_service.GetAllUserEmailsBatch(
        self.cnxn, limit=30, offset=60)
    self.user_service.user_tbl.Select.assert_called_once_with(
        self.cnxn, cols=['email'], limit=30, offset=60,
        where=[('user_id != %s', [framework_constants.DELETED_USER_ID])],
        order_by=[('user_id ASC'), []])
    self.assertItemsEqual(
        emails, ['cow@test.com', 'pig@test.com', 'fox@test.com'])
