# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the usergroup service."""

import collections
import unittest

import mox

from google.appengine.ext import testbed

from framework import permissions
from framework import sql
from proto import usergroup_pb2
from services import service_manager
from services import usergroup_svc
from testing import fake


def MakeUserGroupService(cache_manager, my_mox):
  usergroup_service = usergroup_svc.UserGroupService(cache_manager)
  usergroup_service.usergroup_tbl = my_mox.CreateMock(sql.SQLTableManager)
  usergroup_service.usergroupsettings_tbl = my_mox.CreateMock(
      sql.SQLTableManager)
  usergroup_service.usergroupprojects_tbl = my_mox.CreateMock(
      sql.SQLTableManager)
  return usergroup_service


class MembershipTwoLevelCacheTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cache_manager = fake.CacheManager()
    self.usergroup_service = MakeUserGroupService(self.cache_manager, self.mox)

  def testDeserializeMemberships(self):
    memberships_rows = [(111L, 777L), (111L, 888L), (222L, 888L)]
    actual = self.usergroup_service.memberships_2lc._DeserializeMemberships(
        memberships_rows)
    self.assertItemsEqual([111L, 222L], actual.keys())
    self.assertItemsEqual([777L, 888L], actual[111L])
    self.assertItemsEqual([888L], actual[222L])


class UserGroupServiceTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.mox = mox.Mox()
    self.cnxn = 'fake connection'
    self.cache_manager = fake.CacheManager()
    self.usergroup_service = MakeUserGroupService(self.cache_manager, self.mox)
    self.services = service_manager.Services(
        user=fake.UserService(),
        usergroup=self.usergroup_service,
        project=fake.ProjectService())

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def SetUpCreateGroup(
      self, group_id, visiblity, external_group_type=None):
    self.SetUpUpdateSettings(group_id, visiblity, external_group_type)

  def testCreateGroup_Normal(self):
    self.services.user.TestAddUser('group@example.com', 888L)
    self.SetUpCreateGroup(888L, 'anyone')
    self.mox.ReplayAll()
    actual_group_id = self.usergroup_service.CreateGroup(
        self.cnxn, self.services, 'group@example.com', 'anyone')
    self.mox.VerifyAll()
    self.assertEqual(888L, actual_group_id)

  def testCreateGroup_Import(self):
    self.services.user.TestAddUser('troopers', 888L)
    self.SetUpCreateGroup(888L, 'owners', 'mdb')
    self.mox.ReplayAll()
    actual_group_id = self.usergroup_service.CreateGroup(
        self.cnxn, self.services, 'troopers', 'owners', 'mdb')
    self.mox.VerifyAll()
    self.assertEqual(888L, actual_group_id)

  def SetUpDetermineWhichUserIDsAreGroups(self, ids_to_query, mock_group_ids):
    self.usergroup_service.usergroupsettings_tbl.Select(
        self.cnxn, cols=['group_id'], group_id=ids_to_query).AndReturn(
            (gid,) for gid in mock_group_ids)

  def testDetermineWhichUserIDsAreGroups_NoGroups(self):
    self.SetUpDetermineWhichUserIDsAreGroups([], [])
    self.mox.ReplayAll()
    actual_group_ids = self.usergroup_service.DetermineWhichUserIDsAreGroups(
        self.cnxn, [])
    self.mox.VerifyAll()
    self.assertEqual([], actual_group_ids)

  def testDetermineWhichUserIDsAreGroups_SomeGroups(self):
    user_ids = [111, 222, 333]
    group_ids = [888, 999]
    self.SetUpDetermineWhichUserIDsAreGroups(user_ids + group_ids, group_ids)
    self.mox.ReplayAll()
    actual_group_ids = self.usergroup_service.DetermineWhichUserIDsAreGroups(
        self.cnxn, user_ids + group_ids)
    self.mox.VerifyAll()
    self.assertEqual(group_ids, actual_group_ids)

  def SetUpLookupAllMemberships(self, user_ids, mock_membership_rows):
    self.usergroup_service.usergroup_tbl.Select(
        self.cnxn, cols=['user_id', 'group_id'], distinct=True,
        user_id=user_ids).AndReturn(mock_membership_rows)

  def testLookupAllMemberships(self):
    self.usergroup_service.group_dag.initialized = True
    self.usergroup_service.memberships_2lc.CacheItem(111L, {888L, 999L})
    self.SetUpLookupAllMemberships([222L], [(222L, 777L), (222L, 999L)])
    self.mox.ReplayAll()
    actual_membership_dict = self.usergroup_service.LookupAllMemberships(
        self.cnxn, [111L, 222L])
    self.mox.VerifyAll()
    self.assertEqual(
        {111L: {888L, 999}, 222L: {777L, 999L}},
        actual_membership_dict)

  def SetUpRemoveMembers(self, group_id, member_ids):
    self.usergroup_service.usergroup_tbl.Delete(
        self.cnxn, group_id=group_id, user_id=member_ids)

  def testRemoveMembers(self):
    self.usergroup_service.group_dag.initialized = True
    self.SetUpRemoveMembers(888L, [111L, 222L])
    self.SetUpLookupAllMembers([111L, 222L], [], {}, {})
    self.mox.ReplayAll()
    self.usergroup_service.RemoveMembers(self.cnxn, 888L, [111L, 222L])
    self.mox.VerifyAll()

  def testUpdateMembers(self):
    self.usergroup_service.group_dag.initialized = True
    self.usergroup_service.usergroup_tbl.Delete(
        self.cnxn, group_id=888L, user_id=[111L, 222L])
    self.usergroup_service.usergroup_tbl.InsertRows(
        self.cnxn, ['user_id', 'group_id', 'role'],
        [(111L, 888L, 'member'), (222L, 888L, 'member')])
    self.SetUpLookupAllMembers([111L, 222L], [], {}, {})
    self.mox.ReplayAll()
    self.usergroup_service.UpdateMembers(
        self.cnxn, 888L, [111L, 222L], 'member')
    self.mox.VerifyAll()

  def testUpdateMembers_CircleDetection(self):
    # Two groups: 888 and 999 while 999 is a member of 888.
    self.SetUpDAG([(888,), (999,)], [(999, 888)])
    self.mox.ReplayAll()
    self.assertRaises(
        usergroup_svc.CircularGroupException,
        self.usergroup_service.UpdateMembers, self.cnxn, 999, [888], 'member')
    self.mox.VerifyAll()

  def SetUpLookupAllMembers(
      self, group_ids, direct_member_rows,
      descedants_dict, indirect_member_rows_dict):
    self.usergroup_service.usergroup_tbl.Select(
        self.cnxn, cols=['user_id', 'group_id', 'role'], distinct=True,
        group_id=group_ids).AndReturn(direct_member_rows)
    for gid in group_ids:
      self.usergroup_service.usergroup_tbl.Select(
          self.cnxn, cols=['user_id'], distinct=True,
          group_id=descedants_dict.get(gid, [])).AndReturn(
          indirect_member_rows_dict.get(gid, []))

  def testLookupAllMembers(self):
    self.usergroup_service.group_dag.initialized = True
    self.usergroup_service.group_dag.user_group_children = (
        collections.defaultdict(list))
    self.usergroup_service.group_dag.user_group_children[777] = [888]
    self.usergroup_service.group_dag.user_group_children[888] = [999]
    self.SetUpLookupAllMembers(
        [777],
        [(888, 777, 'member'), (111, 888, 'member'), (999, 888, 'member'),
         (222, 999, 'member')],
        {777: [888, 999]},
        {777: [(111,), (222,), (999,)]})

    self.mox.ReplayAll()
    members_dict, owners_dict = self.usergroup_service.LookupAllMembers(
        self.cnxn, [777])
    self.mox.VerifyAll()
    self.assertItemsEqual([111, 222, 888, 999], members_dict[777])
    self.assertItemsEqual([], owners_dict[777])

  def testExpandAnyUserGroups_NoneRequested(self):
    self.SetUpDetermineWhichUserIDsAreGroups([], [])
    self.SetUpLookupMembers({})
    self.mox.ReplayAll()
    direct_ids, indirect_ids = self.usergroup_service.ExpandAnyUserGroups(
        self.cnxn, [])
    self.mox.VerifyAll()
    self.assertItemsEqual([], direct_ids)
    self.assertItemsEqual([], indirect_ids)

  def testExpandAnyUserGroups_NoGroups(self):
    self.SetUpDetermineWhichUserIDsAreGroups([111, 222], [])
    self.SetUpLookupMembers({})
    self.mox.ReplayAll()
    direct_ids, indirect_ids = self.usergroup_service.ExpandAnyUserGroups(
        self.cnxn, [111, 222])
    self.mox.VerifyAll()
    self.assertItemsEqual([111, 222], direct_ids)
    self.assertItemsEqual([], indirect_ids)

  def testExpandAnyUserGroups_WithGroups(self):
    self.usergroup_service.group_dag.initialized = True
    self.SetUpDetermineWhichUserIDsAreGroups([111, 222, 888], [888])
    self.SetUpLookupAllMembers(
        [888], [(222, 888, 'member'), (333, 888, 'member')], {}, {})
    self.mox.ReplayAll()
    direct_ids, indirect_ids = self.usergroup_service.ExpandAnyUserGroups(
        self.cnxn, [111, 222, 888])
    self.mox.VerifyAll()
    self.assertItemsEqual([111, 222], direct_ids)
    self.assertItemsEqual([333, 222], indirect_ids)

  def SetUpLookupMembers(self, group_member_dict):
    mock_membership_rows = []
    group_ids = []
    for gid, members in group_member_dict.iteritems():
      group_ids.append(gid)
      mock_membership_rows.extend([(uid, gid, 'member') for uid in members])
    group_ids.sort()
    self.usergroup_service.usergroup_tbl.Select(
        self.cnxn, cols=['user_id','group_id', 'role'], distinct=True,
        group_id=group_ids).AndReturn(mock_membership_rows)

  def testLookupMembers_NoneRequested(self):
    self.SetUpLookupMembers({})
    self.mox.ReplayAll()
    member_ids, _ = self.usergroup_service.LookupMembers(self.cnxn, [])
    self.mox.VerifyAll()
    self.assertItemsEqual({}, member_ids)

  def testLookupMembers_Nonexistent(self):
    """If some requested groups don't exist, they are ignored."""
    self.SetUpLookupMembers({777: []})
    self.mox.ReplayAll()
    member_ids, _ = self.usergroup_service.LookupMembers(self.cnxn, [777])
    self.mox.VerifyAll()
    self.assertItemsEqual([], member_ids[777])

  def testLookupMembers_AllEmpty(self):
    """Requesting all empty groups results in no members."""
    self.SetUpLookupMembers({888: [], 999: []})
    self.mox.ReplayAll()
    member_ids, _ = self.usergroup_service.LookupMembers(self.cnxn, [888, 999])
    self.mox.VerifyAll()
    self.assertItemsEqual([], member_ids[888])

  def testLookupMembers_OneGroup(self):
    self.SetUpLookupMembers({888: [111, 222]})
    self.mox.ReplayAll()
    member_ids, _ = self.usergroup_service.LookupMembers(self.cnxn, [888])
    self.mox.VerifyAll()
    self.assertItemsEqual([111, 222], member_ids[888])

  def testLookupMembers_GroupsAndNonGroups(self):
    """We ignore any non-groups passed in."""
    self.SetUpLookupMembers({111: [], 333: [], 888: [111, 222]})
    self.mox.ReplayAll()
    member_ids, _ = self.usergroup_service.LookupMembers(
        self.cnxn, [111, 333, 888])
    self.mox.VerifyAll()
    self.assertItemsEqual([111, 222], member_ids[888])

  def testLookupMembers_OverlappingGroups(self):
    """We get the union of IDs.  Imagine 888 = {111} and 999 = {111, 222}."""
    self.SetUpLookupMembers({888: [111], 999: [111, 222]})
    self.mox.ReplayAll()
    member_ids, _ = self.usergroup_service.LookupMembers(self.cnxn, [888, 999])
    self.mox.VerifyAll()
    self.assertItemsEqual([111, 222], member_ids[999])
    self.assertItemsEqual([111], member_ids[888])

  def testLookupVisibleMembers_LimitedVisiblity(self):
    """We get only the member IDs in groups that the user is allowed to see."""
    self.usergroup_service.group_dag.initialized = True
    self.SetUpGetGroupSettings(
        [888, 999],
        [(888, 'anyone', None, 0), (999, 'members', None, 0)])
    self.SetUpLookupMembers({888: [111], 999: [111]})
    self.SetUpLookupAllMembers(
        [888, 999], [(111, 888, 'member'), (111, 999, 'member')], {}, {})
    self.mox.ReplayAll()
    member_ids, _ = self.usergroup_service.LookupVisibleMembers(
        self.cnxn, [888, 999], permissions.USER_PERMISSIONSET, set(),
        self.services)
    self.mox.VerifyAll()
    self.assertItemsEqual([111], member_ids[888])
    self.assertNotIn(999, member_ids)

  def SetUpGetAllUserGroupsInfo(self, mock_settings_rows, mock_count_rows,
                                mock_friends=None):
    mock_friends = mock_friends or []
    self.usergroup_service.usergroupsettings_tbl.Select(
        self.cnxn, cols=['group_id', 'email', 'who_can_view_members',
                         'external_group_type', 'last_sync_time'],
        left_joins=[('User ON UserGroupSettings.group_id = User.user_id', [])]
        ).AndReturn(mock_settings_rows)
    self.usergroup_service.usergroup_tbl.Select(
        self.cnxn, cols=['group_id', 'COUNT(*)'],
        group_by=['group_id']).AndReturn(mock_count_rows)

    group_ids = [g[0] for g in mock_settings_rows]
    self.usergroup_service.usergroupprojects_tbl.Select(
        self.cnxn, cols=usergroup_svc.USERGROUPPROJECTS_COLS,
        group_id=group_ids).AndReturn(mock_friends)

  def testGetAllUserGroupsInfo(self):
    self.SetUpGetAllUserGroupsInfo(
        [(888L, 'group@example.com', 'anyone', None, 0)],
        [(888L, 12)])
    self.mox.ReplayAll()
    actual_infos = self.usergroup_service.GetAllUserGroupsInfo(self.cnxn)
    self.mox.VerifyAll()
    self.assertEqual(1, len(actual_infos))
    addr, count, group_settings, group_id = actual_infos[0]
    self.assertEqual('group@example.com', addr)
    self.assertEqual(12, count)
    self.assertEqual(usergroup_pb2.MemberVisibility.ANYONE,
                     group_settings.who_can_view_members)
    self.assertEqual(888L, group_id)

  def SetUpGetGroupSettings(self, group_ids, mock_result_rows,
                            mock_friends=None):
    mock_friends = mock_friends or []
    self.usergroup_service.usergroupsettings_tbl.Select(
        self.cnxn, cols=usergroup_svc.USERGROUPSETTINGS_COLS,
        group_id=group_ids).AndReturn(mock_result_rows)
    self.usergroup_service.usergroupprojects_tbl.Select(
        self.cnxn, cols=usergroup_svc.USERGROUPPROJECTS_COLS,
        group_id=group_ids).AndReturn(mock_friends)

  def testGetGroupSettings_NoGroupsRequested(self):
    self.SetUpGetGroupSettings([], [])
    self.mox.ReplayAll()
    actual_settings_dict = self.usergroup_service.GetAllGroupSettings(
        self.cnxn, [])
    self.mox.VerifyAll()
    self.assertEqual({}, actual_settings_dict)

  def testGetGroupSettings_NoGroupsFound(self):
    self.SetUpGetGroupSettings([777L], [])
    self.mox.ReplayAll()
    actual_settings_dict = self.usergroup_service.GetAllGroupSettings(
        self.cnxn, [777L])
    self.mox.VerifyAll()
    self.assertEqual({}, actual_settings_dict)

  def testGetGroupSettings_SomeGroups(self):
    self.SetUpGetGroupSettings(
        [777L, 888L, 999L],
        [(888L, 'anyone', None, 0), (999L, 'members', None, 0)])
    self.mox.ReplayAll()
    actual_settings_dict = self.usergroup_service.GetAllGroupSettings(
        self.cnxn, [777L, 888L, 999L])
    self.mox.VerifyAll()
    self.assertEqual(
        {888L: usergroup_pb2.MakeSettings('anyone'),
         999L: usergroup_pb2.MakeSettings('members')},
        actual_settings_dict)

  def testGetGroupSettings_NoSuchGroup(self):
    self.SetUpGetGroupSettings([777L], [])
    self.mox.ReplayAll()
    actual_settings = self.usergroup_service.GetGroupSettings(self.cnxn, 777L)
    self.mox.VerifyAll()
    self.assertEqual(None, actual_settings)

  def testGetGroupSettings_Found(self):
    self.SetUpGetGroupSettings([888L], [(888L, 'anyone', None, 0)])
    self.mox.ReplayAll()
    actual_settings = self.usergroup_service.GetGroupSettings(self.cnxn, 888)
    self.mox.VerifyAll()
    self.assertEqual(
        usergroup_pb2.MemberVisibility.ANYONE,
        actual_settings.who_can_view_members)

  def testGetGroupSettings_Import(self):
    self.SetUpGetGroupSettings([888L], [(888L, 'owners', 'mdb', 0)])
    self.mox.ReplayAll()
    actual_settings = self.usergroup_service.GetGroupSettings(self.cnxn, 888)
    self.mox.VerifyAll()
    self.assertEqual(
        usergroup_pb2.MemberVisibility.OWNERS,
        actual_settings.who_can_view_members)
    self.assertEqual(
        usergroup_pb2.GroupType.MDB,
        actual_settings.ext_group_type)

  def SetUpUpdateSettings(self, group_id, visiblity, external_group_type=None,
                          last_sync_time=0, friend_projects=None):
    friend_projects = friend_projects or []
    self.usergroup_service.usergroupsettings_tbl.InsertRow(
        self.cnxn, group_id=group_id, who_can_view_members=visiblity,
        external_group_type=external_group_type,
        last_sync_time=last_sync_time,
        replace=True)
    self.usergroup_service.usergroupprojects_tbl.Delete(
        self.cnxn, group_id=group_id)
    if friend_projects:
      rows = [(group_id, p_id) for p_id in friend_projects]
      self.usergroup_service.usergroupprojects_tbl.InsertRows(
        self.cnxn, ['group_id', 'project_id'], rows)

  def testUpdateSettings_Normal(self):
    self.SetUpUpdateSettings(888L, 'anyone')
    self.mox.ReplayAll()
    self.usergroup_service.UpdateSettings(
        self.cnxn, 888L, usergroup_pb2.MakeSettings('anyone'))
    self.mox.VerifyAll()

  def testUpdateSettings_Import(self):
    self.SetUpUpdateSettings(888L, 'owners', 'mdb')
    self.mox.ReplayAll()
    self.usergroup_service.UpdateSettings(
        self.cnxn, 888L,
        usergroup_pb2.MakeSettings('owners', 'mdb'))
    self.mox.VerifyAll()

  def SetUpDAG(self, group_id_rows, usergroup_rows):
    self.usergroup_service.usergroupsettings_tbl.Select(
        self.cnxn, cols=['group_id']).AndReturn(group_id_rows)
    self.usergroup_service.usergroup_tbl.Select(
        self.cnxn, cols=['user_id', 'group_id'], distinct=True,
        user_id=[r[0] for r in group_id_rows]).AndReturn(usergroup_rows)

  def testDAG_Build(self):
    # Old entries should go away after rebuilding
    self.usergroup_service.group_dag.user_group_parents = (
        collections.defaultdict(list))
    self.usergroup_service.group_dag.user_group_parents[111] = [222]
    # Two groups: 888 and 999 while 999 is a member of 888.
    self.SetUpDAG([(888,), (999,)], [(999, 888)])
    self.mox.ReplayAll()
    self.usergroup_service.group_dag.Build(self.cnxn)
    self.mox.VerifyAll()
    self.assertIn(888, self.usergroup_service.group_dag.user_group_children)
    self.assertIn(999, self.usergroup_service.group_dag.user_group_parents)
    self.assertNotIn(111, self.usergroup_service.group_dag.user_group_parents)

  def testDAG_GetAllAncestors(self):
    # Three groups: 777, 888 and 999.
    # 999 is a direct member of 888, and 888 is a direct member of 777.
    self.SetUpDAG([(777,), (888,), (999,)], [(999, 888), (888, 777)])
    self.mox.ReplayAll()
    ancestors = self.usergroup_service.group_dag.GetAllAncestors(
        self.cnxn, 999)
    self.mox.VerifyAll()
    ancestors.sort()
    self.assertEqual([777, 888], ancestors)

  def testDAG_GetAllAncestorsDiamond(self):
    # Four groups: 666, 777, 888 and 999.
    # 999 is a direct member of both 888 and 777,
    # 888 is a direct member of 666, and 777 is also a direct member of 666.
    self.SetUpDAG([(666, ), (777,), (888,), (999,)],
                  [(999, 888), (999, 777), (888, 666), (777, 666)])
    self.mox.ReplayAll()
    ancestors = self.usergroup_service.group_dag.GetAllAncestors(
        self.cnxn, 999)
    self.mox.VerifyAll()
    ancestors.sort()
    self.assertEqual([666, 777, 888], ancestors)

  def testDAG_GetAllDescendants(self):
    # Four groups: 666, 777, 888 and 999.
    # 999 is a direct member of both 888 and 777,
    # 888 is a direct member of 666, and 777 is also a direct member of 666.
    self.SetUpDAG([(666, ), (777,), (888,), (999,)],
                  [(999, 888), (999, 777), (888, 666), (777, 666)])
    self.mox.ReplayAll()
    descendants = self.usergroup_service.group_dag.GetAllDescendants(
        self.cnxn, 666)
    self.mox.VerifyAll()
    descendants.sort()
    self.assertEqual([777, 888, 999], descendants)

  def testDAG_IsChild(self):
    # Four groups: 666, 777, 888 and 999.
    # 999 is a direct member of both 888 and 777,
    # 888 is a direct member of 666, and 777 is also a direct member of 666.
    self.SetUpDAG([(666, ), (777,), (888,), (999,)],
                  [(999, 888), (999, 777), (888, 666), (777, 666)])
    self.mox.ReplayAll()
    result1 = self.usergroup_service.group_dag.IsChild(
        self.cnxn, 777, 666)
    result2 = self.usergroup_service.group_dag.IsChild(
        self.cnxn, 777, 888)
    self.mox.VerifyAll()
    self.assertTrue(result1)
    self.assertFalse(result2)


if __name__ == '__main__':
  unittest.main()
