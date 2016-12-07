# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for features_svc module."""

import unittest
import mox

from google.appengine.api import memcache
from google.appengine.ext import testbed

from features import filterrules_helpers
from features import features_constants
from framework import sql
from services import features_svc
from testing import fake
from tracker import tracker_bizobj
from tracker import tracker_constants


def MakeFeaturesService(cache_manager, my_mox):
  features_service = features_svc.FeaturesService(cache_manager)
  features_service.hotlist_tbl = my_mox.CreateMock(sql.SQLTableManager)
  features_service.hotlist2issue_tbl = my_mox.CreateMock(sql.SQLTableManager)
  features_service.hotlist2user_tbl = my_mox.CreateMock(sql.SQLTableManager)
  return features_service


class HotlistTwoLevelCacheTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.mox = mox.Mox()
    self.cnxn = self.mox.CreateMock(sql.MonorailConnection)
    self.cache_manager = fake.CacheManager()
    self.features_service = MakeFeaturesService(self.cache_manager, self.mox)

  def testDeserializeHotlists(self):
    hotlist_rows = [
        (123, 'hot1', 'test hot 1', 'test hotlist', False, ''),
        (234, 'hot2', 'test hot 2', 'test hotlist', False, '')]
    issue_rows = [
        (123, 567, 10), (123, 678, 9),
        (234, 567, 0)]
    role_rows = [
        (123, 111L, 'owner'), (123, 444L, 'owner'),
        (123, 222L, 'editor'),
        (123, 333L, 'follower'),
        (234, 111L, 'owner')]
    hotlist_dict = self.features_service.hotlist_2lc._DeserializeHotlists(
        hotlist_rows, issue_rows, role_rows)

    self.assertItemsEqual([123, 234], hotlist_dict.keys())
    self.assertEqual(123, hotlist_dict[123].hotlist_id)
    self.assertEqual('hot1', hotlist_dict[123].name)
    self.assertItemsEqual([111L, 444L], hotlist_dict[123].owner_ids)
    self.assertItemsEqual([222L], hotlist_dict[123].editor_ids)
    self.assertItemsEqual([333L], hotlist_dict[123].follower_ids)
    self.assertEqual(234, hotlist_dict[234].hotlist_id)
    self.assertItemsEqual([111L], hotlist_dict[234].owner_ids)


class FeaturesServiceTest(unittest.TestCase):

  def MakeMockTable(self):
    return self.mox.CreateMock(sql.SQLTableManager)

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = self.mox.CreateMock(sql.MonorailConnection)
    self.cache_manager = fake.CacheManager()

    self.features_service = features_svc.FeaturesService(self.cache_manager)

    for table_var in [
        'user2savedquery_tbl', 'quickedithistory_tbl',
        'quickeditmostrecent_tbl', 'savedquery_tbl',
        'savedqueryexecutesinproject_tbl', 'project2savedquery_tbl',
        'filterrule_tbl', 'hotlist_tbl', 'hotlist2issue_tbl',
        'hotlist2user_tbl']:
      setattr(self.features_service, table_var, self.MakeMockTable())

  def tearDown(self):
    memcache.flush_all()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  ### quickedit command history

  def testGetRecentCommands(self):
    self.features_service.quickedithistory_tbl.Select(
        self.cnxn, cols=['slot_num', 'command', 'comment'],
        user_id=1, project_id=12345).AndReturn(
        [(1, 'status=New', 'Brand new issue')])
    self.features_service.quickeditmostrecent_tbl.SelectValue(
        self.cnxn, 'slot_num', default=1, user_id=1, project_id=12345
        ).AndReturn(1)
    self.mox.ReplayAll()
    slots, recent_slot_num = self.features_service.GetRecentCommands(
        self.cnxn, 1, 12345)
    self.mox.VerifyAll()

    self.assertEqual(1, recent_slot_num)
    self.assertEqual(
        len(tracker_constants.DEFAULT_RECENT_COMMANDS), len(slots))
    self.assertEqual('status=New', slots[0][1])

  def testStoreRecentCommand(self):
    self.features_service.quickedithistory_tbl.InsertRow(
        self.cnxn, replace=True, user_id=1, project_id=12345,
        slot_num=1, command='status=New', comment='Brand new issue')
    self.features_service.quickeditmostrecent_tbl.InsertRow(
        self.cnxn, replace=True, user_id=1, project_id=12345,
        slot_num=1)
    self.mox.ReplayAll()
    self.features_service.StoreRecentCommand(
        self.cnxn, 1, 12345, 1, 'status=New', 'Brand new issue')
    self.mox.VerifyAll()

  def testExpungeQuickEditHistory(self):
    self.features_service.quickeditmostrecent_tbl.Delete(
        self.cnxn, project_id=12345)
    self.features_service.quickedithistory_tbl.Delete(
        self.cnxn, project_id=12345)
    self.mox.ReplayAll()
    self.features_service.ExpungeQuickEditHistory(
        self.cnxn, 12345)
    self.mox.VerifyAll()

  ### Saved User and Project Queries

  def testGetSavedQuery_Valid(self):
    self.features_service.savedquery_tbl.Select(
        self.cnxn, cols=features_svc.SAVEDQUERY_COLS, id=[1]).AndReturn(
        [(1, 'query1', 100, 'owner:me')])
    self.features_service.savedqueryexecutesinproject_tbl.Select(
        self.cnxn, cols=features_svc.SAVEDQUERYEXECUTESINPROJECT_COLS,
        query_id=[1]).AndReturn([(1, 12345)])
    self.mox.ReplayAll()
    saved_query = self.features_service.GetSavedQuery(
        self.cnxn, 1)
    self.mox.VerifyAll()
    self.assertEqual(1, saved_query.query_id)
    self.assertEqual('query1', saved_query.name)
    self.assertEqual(100, saved_query.base_query_id)
    self.assertEqual('owner:me', saved_query.query)
    self.assertEqual([12345], saved_query.executes_in_project_ids)

  def testGetSavedQuery_Invalid(self):
    self.features_service.savedquery_tbl.Select(
        self.cnxn, cols=features_svc.SAVEDQUERY_COLS, id=[99]).AndReturn([])
    self.features_service.savedqueryexecutesinproject_tbl.Select(
        self.cnxn, cols=features_svc.SAVEDQUERYEXECUTESINPROJECT_COLS,
        query_id=[99]).AndReturn([])
    self.mox.ReplayAll()
    saved_query = self.features_service.GetSavedQuery(
        self.cnxn, 99)
    self.mox.VerifyAll()
    self.assertIsNone(saved_query)

  def SetUpUsersSavedQueries(self):
    query = tracker_bizobj.MakeSavedQuery(1, 'query1', 100, 'owner:me')
    self.features_service.saved_query_cache.CacheItem(1, [query])
    self.features_service.user2savedquery_tbl.Select(
        self.cnxn,
        cols=features_svc.SAVEDQUERY_COLS + ['user_id', 'subscription_mode'],
        left_joins=[('SavedQuery ON query_id = id', [])],
        order_by=[('rank', [])], user_id=[2]).AndReturn(
        [(2, 'query2', 100, 'status:New', 2, 'Sub_Mode')])
    self.features_service.savedqueryexecutesinproject_tbl.Select(
          self.cnxn, cols=features_svc.SAVEDQUERYEXECUTESINPROJECT_COLS,
          query_id=set([2])).AndReturn([(2, 12345)])

  def testGetUsersSavedQueriesDict(self):
    self.SetUpUsersSavedQueries()
    self.mox.ReplayAll()
    results_dict = self.features_service._GetUsersSavedQueriesDict(
        self.cnxn, [1, 2])
    self.mox.VerifyAll()
    self.assertIn(1, results_dict)
    self.assertIn(2, results_dict)

  def testGetSavedQueriesByUserID(self):
    self.SetUpUsersSavedQueries()
    self.mox.ReplayAll()
    saved_queries = self.features_service.GetSavedQueriesByUserID(
        self.cnxn, 2)
    self.mox.VerifyAll()
    self.assertEqual(1, len(saved_queries))
    self.assertEqual(2, saved_queries[0].query_id)

  def SetUpCannedQueriesForProjects(self):
    self.features_service.project2savedquery_tbl.Select(
        self.cnxn, cols=['project_id'] + features_svc.SAVEDQUERY_COLS,
        left_joins=[('SavedQuery ON query_id = id', [])],
        order_by=[('rank', [])], project_id=[12345]).AndReturn(
        [(12345, 1, 'query1', 100, 'owner:me')])

  def testGetCannedQueriesForProjects(self):
    self.SetUpCannedQueriesForProjects()
    self.mox.ReplayAll()
    results_dict = self.features_service.GetCannedQueriesForProjects(
        self.cnxn, [12345])
    self.mox.VerifyAll()
    self.assertIn(12345, results_dict)

  def testGetCannedQueriesByProjectID(self):
    self.SetUpCannedQueriesForProjects()
    self.mox.ReplayAll()
    result = self.features_service.GetCannedQueriesByProjectID(
        self.cnxn, 12345)
    self.mox.VerifyAll()
    self.assertEqual(1, len(result))
    self.assertEqual(1, result[0].query_id)

  def SetUpUpdateSavedQueries(self, commit=True):
    query1 = tracker_bizobj.MakeSavedQuery(1, 'query1', 100, 'owner:me')
    query2 = tracker_bizobj.MakeSavedQuery(None, 'query2', 100, 'status:New')
    saved_queries = [query1, query2]
    savedquery_rows = [
        (sq.query_id or None, sq.name, sq.base_query_id, sq.query)
        for sq in saved_queries]
    self.features_service.savedquery_tbl.Delete(
        self.cnxn, id=[1], commit=commit)
    self.features_service.savedquery_tbl.InsertRows(
        self.cnxn, features_svc.SAVEDQUERY_COLS, savedquery_rows, commit=commit,
        return_generated_ids=True).AndReturn([11, 12])
    return saved_queries

  def testUpdateSavedQueries(self):
    saved_queries = self.SetUpUpdateSavedQueries()
    self.mox.ReplayAll()
    self.features_service._UpdateSavedQueries(
        self.cnxn, saved_queries, True)
    self.mox.VerifyAll()

  def testUpdateCannedQueries(self):
    self.features_service.project2savedquery_tbl.Delete(
        self.cnxn, project_id=12345, commit=False)
    canned_queries = self.SetUpUpdateSavedQueries(False)
    project2savedquery_rows = [(12345, 0, 1), (12345, 1, 12)]
    self.features_service.project2savedquery_tbl.InsertRows(
        self.cnxn, features_svc.PROJECT2SAVEDQUERY_COLS,
        project2savedquery_rows, commit=False)
    self.cnxn.Commit()
    self.mox.ReplayAll()
    self.features_service.UpdateCannedQueries(
        self.cnxn, 12345, canned_queries)
    self.mox.VerifyAll()

  def testUpdateUserSavedQueries(self):
    saved_queries = self.SetUpUpdateSavedQueries(False)
    self.features_service.savedqueryexecutesinproject_tbl.Delete(
        self.cnxn, query_id=[1], commit=False)
    self.features_service.user2savedquery_tbl.Delete(
        self.cnxn, user_id=1, commit=False)
    user2savedquery_rows = [
      (1, 0, 1, 'noemail'), (1, 1, 12, 'noemail')]
    self.features_service.user2savedquery_tbl.InsertRows(
        self.cnxn, features_svc.USER2SAVEDQUERY_COLS,
        user2savedquery_rows, commit=False)
    self.features_service.savedqueryexecutesinproject_tbl.InsertRows(
        self.cnxn, features_svc.SAVEDQUERYEXECUTESINPROJECT_COLS, [],
        commit=False)
    self.cnxn.Commit()
    self.mox.ReplayAll()
    self.features_service.UpdateUserSavedQueries(
        self.cnxn, 1, saved_queries)
    self.mox.VerifyAll()

  ### Subscriptions

  def testGetSubscriptionsInProjects(self):
    join_str = (
        'SavedQueryExecutesInProject ON '
        'SavedQueryExecutesInProject.query_id = User2SavedQuery.query_id')
    self.features_service.user2savedquery_tbl.Select(
        self.cnxn, cols=['user_id'], distinct=True,
        joins=[(join_str, [])],
        subscription_mode='immediate', project_id=12345).AndReturn(
        [(1, 'asd'), (2, 'efg')])
    self.SetUpUsersSavedQueries()
    self.mox.ReplayAll()
    result = self.features_service.GetSubscriptionsInProjects(
        self.cnxn, 12345)
    self.mox.VerifyAll()
    self.assertIn(1, result)
    self.assertIn(2, result)

  def testExpungeSavedQueriesExecuteInProject(self):
    self.features_service.savedqueryexecutesinproject_tbl.Delete(
        self.cnxn, project_id=12345)
    self.features_service.project2savedquery_tbl.Select(
        self.cnxn, cols=['query_id'], project_id=12345).AndReturn(
        [(1, 'asd'), (2, 'efg')])
    self.features_service.project2savedquery_tbl.Delete(
        self.cnxn, project_id=12345)
    self.features_service.savedquery_tbl.Delete(
        self.cnxn, id=[1, 2])
    self.mox.ReplayAll()
    self.features_service.ExpungeSavedQueriesExecuteInProject(
        self.cnxn, 12345)
    self.mox.VerifyAll()

  ### Filter Rules

  def testDeserializeFilterRules(self):
    filterrule_rows = [
        (12345, 0, 'predicate1', 'default_status:New'),
        (12345, 1, 'predicate2', 'default_owner_id:1 add_cc_id:2'),
    ]
    result_dict = self.features_service._DeserializeFilterRules(
        filterrule_rows)
    self.assertIn(12345, result_dict)
    self.assertEqual(2, len(result_dict[12345]))
    self.assertEqual('New', result_dict[12345][0].default_status)
    self.assertEqual(1, result_dict[12345][1].default_owner_id)
    self.assertEqual([2], result_dict[12345][1].add_cc_ids)

  def testDeserializeRuleConsequence(self):
    consequence = ('default_status:New default_owner_id:1 add_cc_id:2'
                   ' add_label:label1 add_label:label2 add_notify:admin')
    (default_status, default_owner_id, add_cc_ids, add_labels,
     add_notify) = self.features_service._DeserializeRuleConsequence(
        consequence)
    self.assertEqual('New', default_status)
    self.assertEqual(1, default_owner_id)
    self.assertEqual([2], add_cc_ids)
    self.assertEqual(['label1', 'label2'], add_labels)
    self.assertEqual(['admin'], add_notify)

  def SetUpGetFilterRulesByProjectIDs(self):
    filterrule_rows = [
        (12345, 0, 'predicate1', 'default_status:New'),
        (12345, 1, 'predicate2', 'default_owner_id:1 add_cc_id:2'),
    ]

    self.features_service.filterrule_tbl.Select(
        self.cnxn, cols=features_svc.FILTERRULE_COLS,
        project_id=[12345]).AndReturn(filterrule_rows)

  def testGetFilterRulesByProjectIDs(self):
    self.SetUpGetFilterRulesByProjectIDs()
    self.mox.ReplayAll()
    result = self.features_service._GetFilterRulesByProjectIDs(
        self.cnxn, [12345])
    self.mox.VerifyAll()
    self.assertIn(12345, result)
    self.assertEqual(2, len(result[12345]))

  def testGetFilterRules(self):
    self.SetUpGetFilterRulesByProjectIDs()
    self.mox.ReplayAll()
    result = self.features_service.GetFilterRules(
        self.cnxn, 12345)
    self.mox.VerifyAll()
    self.assertEqual(2, len(result))

  def testSerializeRuleConsequence(self):
    rule = filterrules_helpers.MakeRule(
        'predicate', 'New', 1, [1, 2], ['label1', 'label2'], ['admin'])
    result = self.features_service._SerializeRuleConsequence(rule)
    self.assertEqual('add_label:label1 add_label:label2 default_status:New'
                     ' default_owner_id:1 add_cc_id:1 add_cc_id:2'
                     ' add_notify:admin', result)

  def testUpdateFilterRules(self):
    self.features_service.filterrule_tbl.Delete(self.cnxn, project_id=12345)
    rows = [
        (12345, 0, 'predicate1', 'add_label:label1 add_label:label2'
                                 ' default_status:New default_owner_id:1'
                                 ' add_cc_id:1 add_cc_id:2 add_notify:admin'),
        (12345, 1, 'predicate2', 'add_label:label2 add_label:label3'
                                 ' default_status:Fixed default_owner_id:2'
                                 ' add_cc_id:1 add_cc_id:2 add_notify:admin2')
    ]
    self.features_service.filterrule_tbl.InsertRows(
        self.cnxn, features_svc.FILTERRULE_COLS, rows)
    rule1 = filterrules_helpers.MakeRule(
        'predicate1', 'New', 1, [1, 2], ['label1', 'label2'], ['admin'])
    rule2 = filterrules_helpers.MakeRule(
        'predicate2', 'Fixed', 2, [1, 2], ['label2', 'label3'], ['admin2'])
    self.mox.ReplayAll()
    self.features_service.UpdateFilterRules(
        self.cnxn, 12345, [rule1, rule2])
    self.mox.VerifyAll()

  def testExpungeFilterRules(self):
    self.features_service.filterrule_tbl.Delete(self.cnxn, project_id=12345)
    self.mox.ReplayAll()
    self.features_service.ExpungeFilterRules(
        self.cnxn, 12345)
    self.mox.VerifyAll()

  ### Hotlists

  def SetUpCreateHotlist(self):
    # Check for the existing hotlist: there should be none.
    self.features_service.hotlist_tbl.Select(
        self.cnxn, cols=['id', 'name'], name=['hot1']).AndReturn([])

    # Inserting the hotlist returns the id.
    self.features_service.hotlist_tbl.InsertRow(
        self.cnxn, name='hot1', summary='hot 1', description='test hotlist',
        is_private=False,
        default_col_spec=features_constants.DEFAULT_COL_SPEC).AndReturn(123)

    # Insert the issues: there are none.
    self.features_service.hotlist2issue_tbl.InsertRows(
        self.cnxn, ['hotlist_id', 'issue_id', 'rank'], [], commit=False)

    # Insert the users: there is one owner and one editor.
    self.features_service.hotlist2user_tbl.InsertRows(
        self.cnxn, ['hotlist_id', 'user_id', 'role_name'],
        [(123, 567, 'owner'), (123, 678, 'editor')])

  def testCreateHotlist(self):
    self.SetUpCreateHotlist()
    self.mox.ReplayAll()
    self.features_service.CreateHotlist(
        self.cnxn, 'hot1', 'hot 1', 'test hotlist', [567], [678])
    self.mox.VerifyAll()

  def SetUpLookupHotlistIDs(self):
    self.features_service.hotlist_tbl.Select(
        self.cnxn, cols=['id', 'name'], name=['hot1']).AndReturn([
          (123, 'hot1')])
    self.features_service.hotlist2user_tbl.Select(
        self.cnxn, cols=['hotlist_id', 'user_id'], hotlist_id=[123],
        user_id=[567], role_name='owner').AndReturn([(123, 567)])

  def testLookupHotlistIDs(self):
    self.SetUpLookupHotlistIDs()
    self.mox.ReplayAll()
    ret = self.features_service.LookupHotlistIDs(
        self.cnxn, ['hot1'], [567])
    self.assertEqual(ret, {('hot1', 567) : 123})
    self.mox.VerifyAll()

  def SetUpGetHotlists(self, hotlist_id):
    hotlist_rows = [(hotlist_id, 'hotlist2', 'test hotlist 2',
                     'test hotlist', False, '')]
    self.features_service.hotlist_tbl.Select(
        self.cnxn, cols=features_svc.HOTLIST_COLS,
        id=[hotlist_id]).AndReturn(hotlist_rows)
    self.features_service.hotlist2user_tbl.Select(
        self.cnxn, cols=['hotlist_id', 'user_id', 'role_name'],
        hotlist_id=[hotlist_id]).AndReturn([])
    self.features_service.hotlist2issue_tbl.Select(
        self.cnxn, cols=['hotlist_id', 'issue_id', 'rank'],
        hotlist_id=[hotlist_id],
        order_by=[('rank DESC', ''), ('issue_id', '')]).AndReturn([])

  def SetUpUpdateHotlist(self, hotlist_id, delta):
    self.features_service.hotlist_tbl.Update(
        self.cnxn, delta, id=hotlist_id)

  def testUpdateHotlist(self):
    self.SetUpGetHotlists(456)
    delta = {'summary': 'A better one-line summary'}
    self.SetUpUpdateHotlist(456, delta)
    self.mox.ReplayAll()
    self.features_service.UpdateHotlist(
        self.cnxn, 456, summary='A better one-line summary')
    self.mox.VerifyAll()

  def SetUpUpdateHotlistIssuesRankings(self, hotlist_id, relations_to_change):
    self.features_service.hotlist2issue_tbl.Delete(
        self.cnxn, hotlist_id=hotlist_id,
        issue_id=relations_to_change.keys(), commit=False)
    insert_rows = [
        (hotlist_id, issue_id, relations_to_change[
            issue_id]) for issue_id in relations_to_change.keys()]
    self.features_service.hotlist2issue_tbl.InsertRows(
        self.cnxn, cols=features_svc.HOTLIST2ISSUE_COLS,
        row_values=insert_rows, commit=True)

  def testUpdateHotlistIssuesRankings(self):
    self.SetUpGetHotlists(456)
    relations_to_change = {11: 112, 33: 332, 55: 552}
    self.SetUpUpdateHotlistIssuesRankings(456, relations_to_change)
    self.mox.ReplayAll()
    self.features_service.UpdateHotlistIssuesRankings(
        self.cnxn, 456, relations_to_change)
    self.mox.VerifyAll()

  def testGetHotlists(self):
    hotlist1 = fake.Hotlist(hotlist_name='hotlist1', hotlist_id=123)
    self.features_service.hotlist_2lc.CacheItem(123, hotlist1)
    self.SetUpGetHotlists(456)
    self.mox.ReplayAll()
    hotlist_dict = self.features_service.GetHotlists(
        self.cnxn, [123, 456])
    self.mox.VerifyAll()
    self.assertItemsEqual([123, 456], hotlist_dict.keys())
    self.assertEqual('hotlist1', hotlist_dict[123].name)
    self.assertEqual('hotlist2', hotlist_dict[456].name)

  def testGetHotlistsByID(self):
    hotlist1 = fake.Hotlist(hotlist_name='hotlist1', hotlist_id=123)
    self.features_service.hotlist_2lc.CacheItem(123, hotlist1)
    # NOTE: The setup function must take a hotlist_id that is different
    # from what was used in previous tests, otherwise the methods in the
    # setup function will never get called.
    self.SetUpGetHotlists(456)
    self.mox.ReplayAll()
    _, actual_missed = self.features_service.GetHotlistsByID(
        self.cnxn, [123, 456])
    self.mox.VerifyAll()
    self.assertEqual(actual_missed, [])

  def SetUpUpdateHotlistRoles(
      self, hotlist_id, owner_ids, editor_ids, follower_ids):

    self.features_service.hotlist2user_tbl.Delete(
        self.cnxn, hotlist_id=hotlist_id, role_name='owner', commit=False)
    self.features_service.hotlist2user_tbl.Delete(
        self.cnxn, hotlist_id=hotlist_id, role_name='editor', commit=False)
    self.features_service.hotlist2user_tbl.Delete(
        self.cnxn, hotlist_id=hotlist_id, role_name='follower', commit=False)

    self.features_service.hotlist2user_tbl.InsertRows(
        self.cnxn, ['hotlist_id', 'user_id', 'role_name'],
        [(hotlist_id, user_id, 'owner') for user_id in owner_ids],
        commit=False)
    self.features_service.hotlist2user_tbl.InsertRows(
        self.cnxn, ['hotlist_id', 'user_id', 'role_name'],
        [(hotlist_id, user_id, 'editor') for user_id in editor_ids],
        commit=False)
    self.features_service.hotlist2user_tbl.InsertRows(
        self.cnxn, ['hotlist_id', 'user_id', 'role_name'],
        [(hotlist_id, user_id, 'follower') for user_id in follower_ids],
        commit=False)

    self.cnxn.Commit()

  def testUpdateHotlistRoles(self):
    self.SetUpGetHotlists(456)
    self.SetUpUpdateHotlistRoles(456, [111L, 222L], [333L], [])
    self.mox.ReplayAll()
    self.features_service.UpdateHotlistRoles(
        self.cnxn, 456, [111L, 222L], [333L], [])
    self.mox.VerifyAll()

  def SetUpUpdateHotlistIssues(self, cnxn, hotlist_id, _remove, added_pairs):
    self.features_service.hotlist2issue_tbl.Delete(
        cnxn, hotlist_id=hotlist_id, issue_id=[], commit=False)
    insert_rows = [(hotlist_id, issue_id,
        rank) for (issue_id, rank) in added_pairs]
    self.features_service.hotlist2issue_tbl.InsertRows(
        cnxn, cols=features_svc.HOTLIST2ISSUE_COLS,
        row_values=insert_rows, commit=False)

  def testUpdateHotlistIssues(self):
    self.SetUpGetHotlists(456)
    self.SetUpUpdateHotlistIssues(
        self. cnxn, 456, [555L], [(111L, 100), (222L, 200), (333L, 300)])
    self.mox.ReplayAll()
    self.features_service.UpdateHotlistIssues(
        self.cnxn, 456, [555L],
        [(111L, 100), (222L, 200), (333L, 300)], commit=False)
    self.mox.VerifyAll()
