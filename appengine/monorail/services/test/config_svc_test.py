# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for config_svc module."""

import re
import unittest

import mox

from google.appengine.api import memcache
from google.appengine.ext import testbed

from framework import sql
from services import config_svc
from testing import fake
from tracker import tracker_bizobj
from tracker import tracker_constants

LABEL_ROW_SHARDS = config_svc.LABEL_ROW_SHARDS


def MakeConfigService(cache_manager, my_mox):
  config_service = config_svc.ConfigService(cache_manager)
  for table_var in [
      'template_tbl', 'template2label_tbl', 'template2admin_tbl',
      'template2component_tbl', 'template2fieldvalue_tbl',
      'projectissueconfig_tbl', 'statusdef_tbl', 'labeldef_tbl', 'fielddef_tbl',
      'fielddef2admin_tbl', 'componentdef_tbl', 'component2admin_tbl',
      'component2cc_tbl', 'component2label_tbl']:
    setattr(config_service, table_var, my_mox.CreateMock(sql.SQLTableManager))

  return config_service


class LabelRowTwoLevelCacheTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = 'fake connection'
    self.cache_manager = fake.CacheManager()
    self.config_service = MakeConfigService(self.cache_manager, self.mox)
    self.label_row_2lc = self.config_service.label_row_2lc

    self.rows = [(1, 789, 1, 'A', 'doc', False),
                 (2, 789, 2, 'B', 'doc', False),
                 (3, 678, 1, 'C', 'doc', True),
                 (4, 678, None, 'D', 'doc', False)]

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testDeserializeLabelRows_Empty(self):
    label_row_dict = self.label_row_2lc._DeserializeLabelRows([])
    self.assertEqual({}, label_row_dict)

  def testDeserializeLabelRows_Normal(self):
    label_rows_dict = self.label_row_2lc._DeserializeLabelRows(self.rows)
    expected = {
        (789, 1): [(1, 789, 1, 'A', 'doc', False)],
        (789, 2): [(2, 789, 2, 'B', 'doc', False)],
        (678, 3): [(3, 678, 1, 'C', 'doc', True)],
        (678, 4): [(4, 678, None, 'D', 'doc', False)],
        }
    self.assertEqual(expected, label_rows_dict)

  def SetUpFetchItems(self, keys, rows):
    for (project_id, shard_id) in keys:
      sharded_rows = [row for row in rows
                      if row[0] % LABEL_ROW_SHARDS == shard_id]
      self.config_service.labeldef_tbl.Select(
        self.cnxn, cols=config_svc.LABELDEF_COLS, project_id=project_id,
        where=[('id %% %s = %s', [LABEL_ROW_SHARDS, shard_id])]).AndReturn(
        sharded_rows)

  def testFetchItems(self):
    keys = [(567, 0), (678, 0), (789, 0),
            (567, 1), (678, 1), (789, 1),
            (567, 2), (678, 2), (789, 2),
            (567, 3), (678, 3), (789, 3),
            (567, 4), (678, 4), (789, 4),
            ]
    self.SetUpFetchItems(keys, self.rows)
    self.mox.ReplayAll()
    label_rows_dict = self.label_row_2lc.FetchItems(self.cnxn, keys)
    self.mox.VerifyAll()
    expected = {
        (567, 0): [],
        (678, 0): [],
        (789, 0): [],
        (567, 1): [],
        (678, 1): [],
        (789, 1): [(1, 789, 1, 'A', 'doc', False)],
        (567, 2): [],
        (678, 2): [],
        (789, 2): [(2, 789, 2, 'B', 'doc', False)],
        (567, 3): [],
        (678, 3): [(3, 678, 1, 'C', 'doc', True)],
        (789, 3): [],
        (567, 4): [],
        (678, 4): [(4, 678, None, 'D', 'doc', False)],
        (789, 4): [],
        }
    self.assertEqual(expected, label_rows_dict)


class StatusRowTwoLevelCacheTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = 'fake connection'
    self.cache_manager = fake.CacheManager()
    self.config_service = MakeConfigService(self.cache_manager, self.mox)
    self.status_row_2lc = self.config_service.status_row_2lc

    self.rows = [(1, 789, 1, 'A', True, 'doc', False),
                 (2, 789, 2, 'B', False, 'doc', False),
                 (3, 678, 1, 'C', True, 'doc', True),
                 (4, 678, None, 'D', True, 'doc', False)]

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testDeserializeStatusRows_Empty(self):
    status_row_dict = self.status_row_2lc._DeserializeStatusRows([])
    self.assertEqual({}, status_row_dict)

  def testDeserializeStatusRows_Normal(self):
    status_rows_dict = self.status_row_2lc._DeserializeStatusRows(self.rows)
    expected = {
        678: [(3, 678, 1, 'C', True, 'doc', True),
              (4, 678, None, 'D', True, 'doc', False)],
        789: [(1, 789, 1, 'A', True, 'doc', False),
              (2, 789, 2, 'B', False, 'doc', False)],
        }
    self.assertEqual(expected, status_rows_dict)

  def SetUpFetchItems(self, keys, rows):
    self.config_service.statusdef_tbl.Select(
        self.cnxn, cols=config_svc.STATUSDEF_COLS, project_id=keys,
        order_by=[('rank DESC', []), ('status DESC', [])]).AndReturn(
            rows)

  def testFetchItems(self):
    keys = [567, 678, 789]
    self.SetUpFetchItems(keys, self.rows)
    self.mox.ReplayAll()
    status_rows_dict = self.status_row_2lc.FetchItems(self.cnxn, keys)
    self.mox.VerifyAll()
    expected = {
        567: [],
        678: [(3, 678, 1, 'C', True, 'doc', True),
              (4, 678, None, 'D', True, 'doc', False)],
        789: [(1, 789, 1, 'A', True, 'doc', False),
              (2, 789, 2, 'B', False, 'doc', False)],
        }
    self.assertEqual(expected, status_rows_dict)


class ConfigRowTwoLevelCacheTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = 'fake connection'
    self.cache_manager = fake.CacheManager()
    self.config_service = MakeConfigService(self.cache_manager, self.mox)
    self.config_2lc = self.config_service.config_2lc

    self.config_rows = [
      (789, 'Duplicate', 'Pri Type', 1, 2,
       'Type Pri Summary', '-Pri', 'Mstone', 'Owner',
       '', None)]
    self.template_rows = []
    self.template2label_rows = []
    self.template2component_rows = []
    self.template2admin_rows = []
    self.template2fieldvalue_rows = []
    self.statusdef_rows = [(1, 789, 1, 'New', True, 'doc', False),
                           (2, 789, 2, 'Fixed', False, 'doc', False)]
    self.labeldef_rows = [(1, 789, 1, 'Security', 'doc', False),
                          (2, 789, 2, 'UX', 'doc', False)]
    self.fielddef_rows = [(1, 789, None, 'Field', 'INT_TYPE',
                           'Defect', '', False, False, False,
                           1, 99, None, '', '',
                           None, 'NEVER', 'no_action', 'doc', False)]
    self.fielddef2admin_rows = []
    self.componentdef_rows = []
    self.component2admin_rows = []
    self.component2cc_rows = []
    self.component2label_rows = []

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testDeserializeIssueConfigs_Empty(self):
    config_dict = self.config_2lc._DeserializeIssueConfigs(
        [], [], [], [], [], [], [], [], [], [], [], [], [], [])
    self.assertEqual({}, config_dict)

  def testDeserializeIssueConfigs_Normal(self):
    config_dict = self.config_2lc._DeserializeIssueConfigs(
        self.config_rows, self.template_rows, self.template2label_rows,
        self.template2component_rows, self.template2admin_rows,
        self.template2fieldvalue_rows, self.statusdef_rows, self.labeldef_rows,
        self.fielddef_rows, self.fielddef2admin_rows, self.componentdef_rows,
        self.component2admin_rows, self.component2cc_rows,
        self.component2label_rows)
    self.assertItemsEqual([789], config_dict.keys())
    config = config_dict[789]
    self.assertEqual(789, config.project_id)
    self.assertEqual(['Duplicate'], config.statuses_offer_merge)
    self.assertEqual([], config.templates)
    self.assertEqual(len(self.labeldef_rows), len(config.well_known_labels))
    self.assertEqual(len(self.statusdef_rows), len(config.well_known_statuses))
    self.assertEqual(len(self.fielddef_rows), len(config.field_defs))
    self.assertEqual(len(self.componentdef_rows), len(config.component_defs))

  def SetUpFetchConfigs(self, project_ids):
    self.config_service.projectissueconfig_tbl.Select(
        self.cnxn, cols=config_svc.PROJECTISSUECONFIG_COLS,
        project_id=project_ids).AndReturn(self.config_rows)
    self.config_service.template_tbl.Select(
        self.cnxn, cols=config_svc.TEMPLATE_COLS, project_id=project_ids,
        order_by=[('name', [])]).AndReturn(self.template_rows)
    template_ids = [row[0] for row in self.template_rows]
    self.config_service.template2label_tbl.Select(
        self.cnxn, cols=config_svc.TEMPLATE2LABEL_COLS,
        template_id=template_ids).AndReturn(self.template2label_rows)
    self.config_service.template2component_tbl.Select(
        self.cnxn, cols=config_svc.TEMPLATE2COMPONENT_COLS,
        template_id=template_ids).AndReturn(self.template2component_rows)
    self.config_service.template2admin_tbl.Select(
        self.cnxn, cols=config_svc.TEMPLATE2ADMIN_COLS,
        template_id=template_ids).AndReturn(self.template2admin_rows)
    self.config_service.template2fieldvalue_tbl.Select(
        self.cnxn, cols=config_svc.TEMPLATE2FIELDVALUE_COLS,
        template_id=template_ids).AndReturn(self.template2fieldvalue_rows)
    self.config_service.statusdef_tbl.Select(
        self.cnxn, cols=config_svc.STATUSDEF_COLS, project_id=project_ids,
        where=[('rank IS NOT NULL', [])], order_by=[('rank', [])]).AndReturn(
            self.statusdef_rows)
    self.config_service.labeldef_tbl.Select(
        self.cnxn, cols=config_svc.LABELDEF_COLS, project_id=project_ids,
        where=[('rank IS NOT NULL', [])], order_by=[('rank', [])]).AndReturn(
            self.labeldef_rows)
    self.config_service.fielddef_tbl.Select(
        self.cnxn, cols=config_svc.FIELDDEF_COLS, project_id=project_ids,
        order_by=[('field_name', [])]).AndReturn(self.fielddef_rows)
    field_ids = [row[0] for row in self.fielddef_rows]
    self.config_service.fielddef2admin_tbl.Select(
        self.cnxn, cols=config_svc.FIELDDEF2ADMIN_COLS,
        field_id=field_ids).AndReturn(self.fielddef2admin_rows)
    self.config_service.componentdef_tbl.Select(
        self.cnxn, cols=config_svc.COMPONENTDEF_COLS, project_id=project_ids,
        order_by=[('LOWER(path)', [])]).AndReturn(self.componentdef_rows)
    component_ids = [cd_row[0] for cd_row in self.componentdef_rows]
    self.config_service.component2admin_tbl.Select(
        self.cnxn, cols=config_svc.COMPONENT2ADMIN_COLS,
        component_id=component_ids).AndReturn(self.component2admin_rows)
    self.config_service.component2cc_tbl.Select(
        self.cnxn, cols=config_svc.COMPONENT2CC_COLS,
        component_id=component_ids).AndReturn(self.component2cc_rows)
    self.config_service.component2label_tbl.Select(
        self.cnxn, cols=config_svc.COMPONENT2LABEL_COLS,
        component_id=component_ids).AndReturn(self.component2label_rows)

  def testFetchConfigs(self):
    keys = [789]
    self.SetUpFetchConfigs(keys)
    self.mox.ReplayAll()
    config_dict = self.config_2lc._FetchConfigs(self.cnxn, keys)
    self.mox.VerifyAll()
    self.assertItemsEqual(keys, config_dict.keys())

  def testFetchItems(self):
    keys = [678, 789]
    self.SetUpFetchConfigs(keys)
    self.mox.ReplayAll()
    config_dict = self.config_2lc.FetchItems(self.cnxn, keys)
    self.mox.VerifyAll()
    self.assertItemsEqual(keys, config_dict.keys())


class ConfigServiceTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.mox = mox.Mox()
    self.cnxn = self.mox.CreateMock(sql.MonorailConnection)
    self.cache_manager = fake.CacheManager()
    self.config_service = MakeConfigService(self.cache_manager, self.mox)

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  ### Label lookups

  def testGetLabelDefRows_Hit(self):
    self.config_service.label_row_2lc.CacheItem((789, 0), [])
    self.config_service.label_row_2lc.CacheItem((789, 1), [])
    self.config_service.label_row_2lc.CacheItem((789, 2), [])
    self.config_service.label_row_2lc.CacheItem(
        (789, 3), [(3, 678, 1, 'C', 'doc', True)])
    self.config_service.label_row_2lc.CacheItem(
        (789, 4), [(4, 678, None, 'D', 'doc', False)])
    self.config_service.label_row_2lc.CacheItem((789, 5), [])
    self.config_service.label_row_2lc.CacheItem((789, 6), [])
    self.config_service.label_row_2lc.CacheItem((789, 7), [])
    self.config_service.label_row_2lc.CacheItem((789, 8), [])
    self.config_service.label_row_2lc.CacheItem((789, 9), [])
    actual = self.config_service.GetLabelDefRows(self.cnxn, 789)
    expected = [
      (3, 678, 1, 'C', 'doc', True),
      (4, 678, None, 'D', 'doc', False)]
    self.assertEqual(expected, actual)

  def SetUpGetLabelDefRowsAnyProject(self, rows):
    self.config_service.labeldef_tbl.Select(
        self.cnxn, cols=config_svc.LABELDEF_COLS, where=None,
        order_by=[('rank DESC', []), ('label DESC', [])]).AndReturn(
            rows)

  def testGetLabelDefRowsAnyProject(self):
    rows = 'foo'
    self.SetUpGetLabelDefRowsAnyProject(rows)
    self.mox.ReplayAll()
    actual = self.config_service.GetLabelDefRowsAnyProject(self.cnxn)
    self.mox.VerifyAll()
    self.assertEqual(rows, actual)

  def testDeserializeLabels(self):
    labeldef_rows = [(1, 789, 1, 'Security', 'doc', False),
                     (2, 789, 2, 'UX', 'doc', True)]
    id_to_name, name_to_id = self.config_service._DeserializeLabels(
        labeldef_rows)
    self.assertEqual({1: 'Security', 2: 'UX'}, id_to_name)
    self.assertEqual({'security': 1, 'ux': 2}, name_to_id)

  def testEnsureLabelCacheEntry_Hit(self):
    label_dicts = 'foo'
    self.config_service.label_cache.CacheItem(789, label_dicts)
    # No mock calls set up because none are needed.
    self.mox.ReplayAll()
    self.config_service._EnsureLabelCacheEntry(self.cnxn, 789)
    self.mox.VerifyAll()

  def SetUpEnsureLabelCacheEntry_Miss(self, project_id, rows):
    for shard_id in range(0, LABEL_ROW_SHARDS):
      shard_rows = [row for row in rows
                    if row[0] % LABEL_ROW_SHARDS == shard_id]
      self.config_service.labeldef_tbl.Select(
        self.cnxn, cols=config_svc.LABELDEF_COLS, project_id=project_id,
        where=[('id %% %s = %s', [LABEL_ROW_SHARDS, shard_id])]).AndReturn(
            shard_rows)

  def testEnsureLabelCacheEntry_Miss(self):
    labeldef_rows = [(1, 789, 1, 'Security', 'doc', False),
                     (2, 789, 2, 'UX', 'doc', True)]
    self.SetUpEnsureLabelCacheEntry_Miss(789, labeldef_rows)
    self.mox.ReplayAll()
    self.config_service._EnsureLabelCacheEntry(self.cnxn, 789)
    self.mox.VerifyAll()
    label_dicts = {1: 'Security', 2: 'UX'}, {'security': 1, 'ux': 2}
    self.assertEqual(label_dicts, self.config_service.label_cache.GetItem(789))

  def testLookupLabel_Hit(self):
    label_dicts = {1: 'Security', 2: 'UX'}, {'security': 1, 'ux': 2}
    self.config_service.label_cache.CacheItem(789, label_dicts)
    # No mock calls set up because none are needed.
    self.mox.ReplayAll()
    self.assertEqual(
        'Security', self.config_service.LookupLabel(self.cnxn, 789, 1))
    self.assertEqual(
        'UX', self.config_service.LookupLabel(self.cnxn, 789, 2))
    self.mox.VerifyAll()

  def testLookupLabelID_Hit(self):
    label_dicts = {1: 'Security', 2: 'UX'}, {'security': 1, 'ux': 2}
    self.config_service.label_cache.CacheItem(789, label_dicts)
    # No mock calls set up because none are needed.
    self.mox.ReplayAll()
    self.assertEqual(
        1, self.config_service.LookupLabelID(self.cnxn, 789, 'Security'))
    self.assertEqual(
        2, self.config_service.LookupLabelID(self.cnxn, 789, 'UX'))
    self.mox.VerifyAll()

  def testLookupLabelID_MissAndDoubleCheck(self):
    label_dicts = {1: 'Security', 2: 'UX'}, {'security': 1, 'ux': 2}
    self.config_service.label_cache.CacheItem(789, label_dicts)

    self.config_service.labeldef_tbl.Select(
        self.cnxn, cols=['id'], project_id=789,
        where=[('LOWER(label) = %s', ['newlabel'])],
        limit=1).AndReturn([(3,)])
    self.mox.ReplayAll()
    self.assertEqual(
        3, self.config_service.LookupLabelID(self.cnxn, 789, 'NewLabel'))
    self.mox.VerifyAll()

  def testLookupLabelID_MissAutocreate(self):
    label_dicts = {1: 'Security', 2: 'UX'}, {'security': 1, 'ux': 2}
    self.config_service.label_cache.CacheItem(789, label_dicts)

    self.config_service.labeldef_tbl.Select(
        self.cnxn, cols=['id'], project_id=789,
        where=[('LOWER(label) = %s', ['newlabel'])],
        limit=1).AndReturn([])
    self.config_service.labeldef_tbl.InsertRow(
        self.cnxn, project_id=789, label='NewLabel').AndReturn(3)
    self.mox.ReplayAll()
    self.assertEqual(
        3, self.config_service.LookupLabelID(self.cnxn, 789, 'NewLabel'))
    self.mox.VerifyAll()

  def testLookupLabelID_MissDontAutocreate(self):
    label_dicts = {1: 'Security', 2: 'UX'}, {'security': 1, 'ux': 2}
    self.config_service.label_cache.CacheItem(789, label_dicts)

    self.config_service.labeldef_tbl.Select(
        self.cnxn, cols=['id'], project_id=789,
        where=[('LOWER(label) = %s', ['newlabel'])],
        limit=1).AndReturn([])
    self.mox.ReplayAll()
    self.assertIsNone(self.config_service.LookupLabelID(
        self.cnxn, 789, 'NewLabel', autocreate=False))
    self.mox.VerifyAll()

  def testLookupLabelIDs_Hit(self):
    label_dicts = {1: 'Security', 2: 'UX'}, {'security': 1, 'ux': 2}
    self.config_service.label_cache.CacheItem(789, label_dicts)
    # No mock calls set up because none are needed.
    self.mox.ReplayAll()
    self.assertEqual(
        [1, 2],
        self.config_service.LookupLabelIDs(self.cnxn, 789, ['Security', 'UX']))
    self.mox.VerifyAll()

  def testLookupIDsOfLabelsMatching_Hit(self):
    label_dicts = {1: 'Security', 2: 'UX'}, {'security': 1, 'ux': 2}
    self.config_service.label_cache.CacheItem(789, label_dicts)
    # No mock calls set up because none are needed.
    self.mox.ReplayAll()
    self.assertItemsEqual(
        [1],
        self.config_service.LookupIDsOfLabelsMatching(
            self.cnxn, 789, re.compile('Sec.*')))
    self.assertItemsEqual(
        [1, 2],
        self.config_service.LookupIDsOfLabelsMatching(
            self.cnxn, 789, re.compile('.*')))
    self.assertItemsEqual(
        [],
        self.config_service.LookupIDsOfLabelsMatching(
            self.cnxn, 789, re.compile('Zzzzz.*')))
    self.mox.VerifyAll()

  def SetUpLookupLabelIDsAnyProject(self, label, id_rows):
    self.config_service.labeldef_tbl.Select(
        self.cnxn, cols=['id'], label=label).AndReturn(id_rows)

  def testLookupLabelIDsAnyProject(self):
    self.SetUpLookupLabelIDsAnyProject('Security', [(1,)])
    self.mox.ReplayAll()
    actual = self.config_service.LookupLabelIDsAnyProject(
        self.cnxn, 'Security')
    self.mox.VerifyAll()
    self.assertEqual([1], actual)

  def SetUpLookupIDsOfLabelsMatchingAnyProject(self, id_label_rows):
    self.config_service.labeldef_tbl.Select(
        self.cnxn, cols=['id', 'label']).AndReturn(id_label_rows)

  def testLookupIDsOfLabelsMatchingAnyProject(self):
    id_label_rows = [(1, 'Security'), (2, 'UX')]
    self.SetUpLookupIDsOfLabelsMatchingAnyProject(id_label_rows)
    self.mox.ReplayAll()
    actual = self.config_service.LookupIDsOfLabelsMatchingAnyProject(
        self.cnxn, re.compile('(Sec|Zzz).*'))
    self.mox.VerifyAll()
    self.assertEqual([1], actual)

  ### Status lookups

  def testGetStatusDefRows(self):
    rows = 'foo'
    self.config_service.status_row_2lc.CacheItem(789, rows)
    actual = self.config_service.GetStatusDefRows(self.cnxn, 789)
    self.assertEqual(rows, actual)

  def SetUpGetStatusDefRowsAnyProject(self, rows):
    self.config_service.statusdef_tbl.Select(
        self.cnxn, cols=config_svc.STATUSDEF_COLS,
        order_by=[('rank DESC', []), ('status DESC', [])]).AndReturn(
            rows)

  def testGetStatusDefRowsAnyProject(self):
    rows = 'foo'
    self.SetUpGetStatusDefRowsAnyProject(rows)
    self.mox.ReplayAll()
    actual = self.config_service.GetStatusDefRowsAnyProject(self.cnxn)
    self.mox.VerifyAll()
    self.assertEqual(rows, actual)

  def testDeserializeStatuses(self):
    statusdef_rows = [(1, 789, 1, 'New', True, 'doc', False),
                      (2, 789, 2, 'Fixed', False, 'doc', True)]
    actual = self.config_service._DeserializeStatuses(statusdef_rows)
    id_to_name, name_to_id, closed_ids = actual
    self.assertEqual({1: 'New', 2: 'Fixed'}, id_to_name)
    self.assertEqual({'new': 1, 'fixed': 2}, name_to_id)
    self.assertEqual([2], closed_ids)

  def testEnsureStatusCacheEntry_Hit(self):
    status_dicts = 'foo'
    self.config_service.status_cache.CacheItem(789, status_dicts)
    # No mock calls set up because none are needed.
    self.mox.ReplayAll()
    self.config_service._EnsureStatusCacheEntry(self.cnxn, 789)
    self.mox.VerifyAll()

  def SetUpEnsureStatusCacheEntry_Miss(self, keys, rows):
    self.config_service.statusdef_tbl.Select(
        self.cnxn, cols=config_svc.STATUSDEF_COLS, project_id=keys,
        order_by=[('rank DESC', []), ('status DESC', [])]).AndReturn(
            rows)

  def testEnsureStatusCacheEntry_Miss(self):
    statusdef_rows = [(1, 789, 1, 'New', True, 'doc', False),
                      (2, 789, 2, 'Fixed', False, 'doc', True)]
    self.SetUpEnsureStatusCacheEntry_Miss([789], statusdef_rows)
    self.mox.ReplayAll()
    self.config_service._EnsureStatusCacheEntry(self.cnxn, 789)
    self.mox.VerifyAll()
    status_dicts = {1: 'New', 2: 'Fixed'}, {'new': 1, 'fixed': 2}, [2]
    self.assertEqual(
        status_dicts, self.config_service.status_cache.GetItem(789))

  def testLookupStatus_Hit(self):
    status_dicts = {1: 'New', 2: 'Fixed'}, {'new': 1, 'fixed': 2}, [2]
    self.config_service.status_cache.CacheItem(789, status_dicts)
    # No mock calls set up because none are needed.
    self.mox.ReplayAll()
    self.assertEqual(
        'New', self.config_service.LookupStatus(self.cnxn, 789, 1))
    self.assertEqual(
        'Fixed', self.config_service.LookupStatus(self.cnxn, 789, 2))
    self.mox.VerifyAll()

  def testLookupStatusID_Hit(self):
    status_dicts = {1: 'New', 2: 'Fixed'}, {'new': 1, 'fixed': 2}, [2]
    self.config_service.status_cache.CacheItem(789, status_dicts)
    # No mock calls set up because none are needed.
    self.mox.ReplayAll()
    self.assertEqual(
        1, self.config_service.LookupStatusID(self.cnxn, 789, 'New'))
    self.assertEqual(
        2, self.config_service.LookupStatusID(self.cnxn, 789, 'Fixed'))
    self.mox.VerifyAll()

  def testLookupStatusIDs_Hit(self):
    status_dicts = {1: 'New', 2: 'Fixed'}, {'new': 1, 'fixed': 2}, [2]
    self.config_service.status_cache.CacheItem(789, status_dicts)
    # No mock calls set up because none are needed.
    self.mox.ReplayAll()
    self.assertEqual(
        [1, 2],
        self.config_service.LookupStatusIDs(self.cnxn, 789, ['New', 'Fixed']))
    self.mox.VerifyAll()

  def testLookupClosedStatusIDs_Hit(self):
    status_dicts = {1: 'New', 2: 'Fixed'}, {'new': 1, 'fixed': 2}, [2]
    self.config_service.status_cache.CacheItem(789, status_dicts)
    # No mock calls set up because none are needed.
    self.mox.ReplayAll()
    self.assertEqual(
        [2],
        self.config_service.LookupClosedStatusIDs(self.cnxn, 789))
    self.mox.VerifyAll()

  def SetUpLookupClosedStatusIDsAnyProject(self, id_rows):
    self.config_service.statusdef_tbl.Select(
        self.cnxn, cols=['id'], means_open=False).AndReturn(
            id_rows)

  def testLookupClosedStatusIDsAnyProject(self):
    self.SetUpLookupClosedStatusIDsAnyProject([(2,)])
    self.mox.ReplayAll()
    actual = self.config_service.LookupClosedStatusIDsAnyProject(self.cnxn)
    self.mox.VerifyAll()
    self.assertEqual([2], actual)

  def SetUpLookupStatusIDsAnyProject(self, status, id_rows):
    self.config_service.statusdef_tbl.Select(
        self.cnxn, cols=['id'], status=status).AndReturn(id_rows)

  def testLookupStatusIDsAnyProject(self):
    self.SetUpLookupStatusIDsAnyProject('New', [(1,)])
    self.mox.ReplayAll()
    actual = self.config_service.LookupStatusIDsAnyProject(self.cnxn, 'New')
    self.mox.VerifyAll()
    self.assertEqual([1], actual)

  ### Issue tracker configuration objects

  def SetUpGetProjectConfigs(self, project_ids):
    self.config_service.projectissueconfig_tbl.Select(
        self.cnxn, cols=config_svc.PROJECTISSUECONFIG_COLS,
        project_id=project_ids).AndReturn([])
    self.config_service.template_tbl.Select(
        self.cnxn, cols=config_svc.TEMPLATE_COLS,
        project_id=project_ids, order_by=[('name', [])]).AndReturn([])
    self.config_service.template2label_tbl.Select(
        self.cnxn, cols=config_svc.TEMPLATE2LABEL_COLS,
        template_id=[]).AndReturn([])
    self.config_service.template2component_tbl.Select(
        self.cnxn, cols=config_svc.TEMPLATE2COMPONENT_COLS,
        template_id=[]).AndReturn([])
    self.config_service.template2admin_tbl.Select(
        self.cnxn, cols=config_svc.TEMPLATE2ADMIN_COLS,
        template_id=[]).AndReturn([])
    self.config_service.template2fieldvalue_tbl.Select(
        self.cnxn, cols=config_svc.TEMPLATE2FIELDVALUE_COLS,
        template_id=[]).AndReturn([])
    self.config_service.statusdef_tbl.Select(
        self.cnxn, cols=config_svc.STATUSDEF_COLS,
        project_id=project_ids, where=[('rank IS NOT NULL', [])],
        order_by=[('rank', [])]).AndReturn([])
    self.config_service.labeldef_tbl.Select(
        self.cnxn, cols=config_svc.LABELDEF_COLS,
        project_id=project_ids, where=[('rank IS NOT NULL', [])],
        order_by=[('rank', [])]).AndReturn([])
    self.config_service.fielddef_tbl.Select(
        self.cnxn, cols=config_svc.FIELDDEF_COLS,
        project_id=project_ids, order_by=[('field_name', [])]).AndReturn([])
    self.config_service.fielddef2admin_tbl.Select(
        self.cnxn, cols=config_svc.FIELDDEF2ADMIN_COLS,
        field_id=[]).AndReturn([])
    self.config_service.componentdef_tbl.Select(
        self.cnxn, cols=config_svc.COMPONENTDEF_COLS,
        project_id=project_ids, order_by=[('LOWER(path)', [])]).AndReturn([])
    self.config_service.component2admin_tbl.Select(
        self.cnxn, cols=config_svc.COMPONENT2ADMIN_COLS,
        component_id=[]).AndReturn([])
    self.config_service.component2cc_tbl.Select(
        self.cnxn, cols=config_svc.COMPONENT2CC_COLS,
        component_id=[]).AndReturn([])
    self.config_service.component2label_tbl.Select(
        self.cnxn, cols=config_svc.COMPONENT2LABEL_COLS,
        component_id=[]).AndReturn([])

  def testGetProjectConfigs(self):
    project_ids = [789, 679]
    self.SetUpGetProjectConfigs(project_ids)

    self.mox.ReplayAll()
    config_dict = self.config_service.GetProjectConfigs(
        self.cnxn, [789, 679], use_cache=False)
    self.assertEqual(2, len(config_dict))
    for pid in project_ids:
      self.assertEqual(pid, config_dict[pid].project_id)
    self.mox.VerifyAll()

  def testGetProjectConfig_Hit(self):
    project_id = 789
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(project_id)
    self.config_service.config_2lc.CacheItem(project_id, config)

    self.mox.ReplayAll()
    actual = self.config_service.GetProjectConfig(self.cnxn, project_id)
    self.assertEqual(config, actual)
    self.mox.VerifyAll()

  def testGetProjectConfig_Miss(self):
    project_id = 789
    self.SetUpGetProjectConfigs([project_id])

    self.mox.ReplayAll()
    config = self.config_service.GetProjectConfig(self.cnxn, project_id)
    self.assertEqual(project_id, config.project_id)
    self.mox.VerifyAll()

  def SetUpStoreConfig_Default(self, project_id):
    self.config_service.projectissueconfig_tbl.InsertRow(
        self.cnxn, replace=True,
        project_id=project_id,
        statuses_offer_merge='Duplicate',
        exclusive_label_prefixes='Type Priority Milestone',
        default_template_for_developers=0,
        default_template_for_users=0,
        default_col_spec=tracker_constants.DEFAULT_COL_SPEC,
        default_sort_spec='',
        default_x_attr='',
        default_y_attr='',
        member_default_query='',
        custom_issue_entry_url=None,
        commit=False)

    self.SetUpUpdateTemplates_Default(project_id)
    self.SetUpUpdateWellKnownLabels_Default(project_id)
    self.SetUpUpdateWellKnownStatuses_Default(project_id)
    self.cnxn.Commit()

  def SetUpUpdateTemplates_Default(self, project_id):
    self.config_service.template_tbl.Select(
      self.cnxn, cols=['id'], project_id=project_id).AndReturn([])
    self.config_service.template2label_tbl.Delete(
      self.cnxn, template_id=[], commit=False)
    self.config_service.template2component_tbl.Delete(
      self.cnxn, template_id=[], commit=False)
    self.config_service.template2admin_tbl.Delete(
      self.cnxn, template_id=[], commit=False)
    self.config_service.template2fieldvalue_tbl.Delete(
      self.cnxn, template_id=[], commit=False)
    self.config_service.template_tbl.Delete(
      self.cnxn, project_id=project_id, commit=False)

    template_rows = []
    for template_dict in tracker_constants.DEFAULT_TEMPLATES:
      row = (None,
             project_id,
             template_dict['name'],
             template_dict['content'],
             template_dict['summary'],
             template_dict.get('summary_must_be_edited'),
             None,
             template_dict['status'],
             template_dict.get('members_only', False),
             template_dict.get('owner_defaults_to_member', True),
             template_dict.get('component_required', False))
      template_rows.append(row)

    self.config_service.template_tbl.InsertRows(
        self.cnxn, config_svc.TEMPLATE_COLS, template_rows,
        replace=True, commit=False, return_generated_ids=True).AndReturn(
        range(1, len(template_rows) + 1))

    template2label_rows = [
        (2, 'Type-Defect'),
        (2, 'Priority-Medium'),
        (1, 'Type-Defect'),
        (1, 'Priority-Medium'),
        ]
    template2component_rows = []
    template2admin_rows = []
    template2fieldvalue_rows = []

    self.config_service.template2label_tbl.InsertRows(
        self.cnxn, config_svc.TEMPLATE2LABEL_COLS, template2label_rows,
        ignore=True, commit=False)
    self.config_service.template2component_tbl.InsertRows(
        self.cnxn, config_svc.TEMPLATE2COMPONENT_COLS, template2component_rows,
        commit=False)
    self.config_service.template2admin_tbl.InsertRows(
        self.cnxn, config_svc.TEMPLATE2ADMIN_COLS, template2admin_rows,
        commit=False)
    self.config_service.template2fieldvalue_tbl.InsertRows(
        self.cnxn, config_svc.TEMPLATE2FIELDVALUE_COLS,
        template2fieldvalue_rows, commit=False)

  def SetUpUpdateWellKnownLabels_Default(self, project_id):
    by_id = {
        idx + 1: label for idx, (label, _, _) in enumerate(
            tracker_constants.DEFAULT_WELL_KNOWN_LABELS)}
    by_name = {name.lower(): label_id
               for label_id, name in by_id.iteritems()}
    label_dicts = by_id, by_name
    self.config_service.label_cache.CacheAll({789: label_dicts})

    update_labeldef_rows = [
        (idx + 1, project_id, idx, label, doc, deprecated)
        for idx, (label, doc, deprecated) in enumerate(
            tracker_constants.DEFAULT_WELL_KNOWN_LABELS)]
    self.config_service.labeldef_tbl.Update(
        self.cnxn, {'rank': None}, project_id=project_id, commit=False)
    self.config_service.labeldef_tbl.InsertRows(
        self.cnxn, config_svc.LABELDEF_COLS, update_labeldef_rows,
        replace=True, commit=False)
    self.config_service.labeldef_tbl.InsertRows(
        self.cnxn, config_svc.LABELDEF_COLS[1:], [], commit=False)

  def SetUpUpdateWellKnownStatuses_Default(self, project_id):
    by_id = {
        idx + 1: status for idx, (status, _, _, _) in enumerate(
            tracker_constants.DEFAULT_WELL_KNOWN_STATUSES)}
    by_name = {name.lower(): label_id
               for label_id, name in by_id.iteritems()}
    closed_ids = [
        idx + 1 for idx, (_, _, means_open, _) in enumerate(
            tracker_constants.DEFAULT_WELL_KNOWN_STATUSES)
        if not means_open]
    status_dicts = by_id, by_name, closed_ids
    self.config_service.status_cache.CacheAll({789: status_dicts})

    update_statusdef_rows = [
        (idx + 1, project_id, idx, status, means_open, doc, deprecated)
        for idx, (status, doc, means_open, deprecated) in enumerate(
            tracker_constants.DEFAULT_WELL_KNOWN_STATUSES)]
    self.config_service.statusdef_tbl.Update(
        self.cnxn, {'rank': None}, project_id=project_id, commit=False)
    self.config_service.statusdef_tbl.InsertRows(
        self.cnxn, config_svc.STATUSDEF_COLS, update_statusdef_rows,
        replace=True, commit=False)
    self.config_service.statusdef_tbl.InsertRows(
        self.cnxn, config_svc.STATUSDEF_COLS[1:], [], commit=False)

  def testStoreConfig(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.SetUpStoreConfig_Default(789)

    self.mox.ReplayAll()
    self.config_service.StoreConfig(self.cnxn, config)
    self.mox.VerifyAll()

  def testUpdateTemplates(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.SetUpUpdateTemplates_Default(789)

    self.mox.ReplayAll()
    self.config_service._UpdateTemplates(self.cnxn, config)
    self.mox.VerifyAll()

  def testUpdateWellKnownLabels(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.SetUpUpdateWellKnownLabels_Default(789)

    self.mox.ReplayAll()
    self.config_service._UpdateWellKnownLabels(self.cnxn, config)
    self.mox.VerifyAll()

  def testUpdateWellKnownStatuses(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.SetUpUpdateWellKnownStatuses_Default(789)

    self.mox.ReplayAll()
    self.config_service._UpdateWellKnownStatuses(self.cnxn, config)
    self.mox.VerifyAll()

  def testUpdateConfig(self):
    pass  # TODO(jrobbins): add a test for this

  def SetUpExpungeConfig(self, project_id):
    self.config_service.template_tbl.Select(
        self.cnxn, cols=['id'], project_id=project_id).AndReturn([])
    self.config_service.template2label_tbl.Delete(self.cnxn, template_id=[])
    self.config_service.template2component_tbl.Delete(self.cnxn, template_id=[])
    self.config_service.template_tbl.Delete(self.cnxn, project_id=project_id)
    self.config_service.statusdef_tbl.Delete(self.cnxn, project_id=project_id)
    self.config_service.labeldef_tbl.Delete(self.cnxn, project_id=project_id)
    self.config_service.projectissueconfig_tbl.Delete(
        self.cnxn, project_id=project_id)

    self.config_service.config_2lc.InvalidateKeys(self.cnxn, [project_id])

  def testExpungeConfig(self):
    self.SetUpExpungeConfig(789)

    self.mox.ReplayAll()
    self.config_service.ExpungeConfig(self.cnxn, 789)
    self.mox.VerifyAll()

  ### Custom field definitions

  def SetUpCreateFieldDef(self, project_id):
    self.config_service.fielddef_tbl.InsertRow(
        self.cnxn, project_id=project_id,
        field_name='PercentDone', field_type='int_type',
        applicable_type='Defect', applicable_predicate='',
        is_required=False, is_multivalued=False, is_niche=False,
        min_value=1, max_value=100, regex=None,
        needs_member=None, needs_perm=None,
        grants_perm=None, notify_on='never', date_action='no_action',
        docstring='doc', commit=False).AndReturn(1)
    self.config_service.fielddef2admin_tbl.InsertRows(
        self.cnxn, config_svc.FIELDDEF2ADMIN_COLS, [], commit=False)
    self.cnxn.Commit()

  def testCreateFieldDef(self):
    self.SetUpCreateFieldDef(789)

    self.mox.ReplayAll()
    field_id = self.config_service.CreateFieldDef(
        self.cnxn, 789, 'PercentDone', 'int_type', 'Defect', '', False, False,
        False, 1, 100, None, None, None, None, 0, 'no_action', 'doc', [])
    self.mox.VerifyAll()
    self.assertEqual(1, field_id)

  def SetUpSoftDeleteFieldDef(self, field_id):
    self.config_service.fielddef_tbl.Update(
        self.cnxn, {'is_deleted': True}, id=field_id)

  def testSoftDeleteFieldDef(self):
    self.SetUpSoftDeleteFieldDef(1)

    self.mox.ReplayAll()
    self.config_service.SoftDeleteFieldDef(self.cnxn, 789, 1)
    self.mox.VerifyAll()

  def SetUpUpdateFieldDef(self, field_id, new_values):
    self.config_service.fielddef_tbl.Update(
        self.cnxn, new_values, id=field_id, commit=False)
    self.config_service.fielddef2admin_tbl.Delete(
        self.cnxn, field_id=field_id, commit=False)
    self.config_service.fielddef2admin_tbl.InsertRows(
        self.cnxn, config_svc.FIELDDEF2ADMIN_COLS, [], commit=False)
    self.cnxn.Commit()

  def testUpdateFieldDef_NoOp(self):
    new_values = {}
    self.SetUpUpdateFieldDef(1, new_values)

    self.mox.ReplayAll()
    self.config_service.UpdateFieldDef(self.cnxn, 789, 1, admin_ids=[])
    self.mox.VerifyAll()

  def testUpdateFieldDef_Normal(self):
    new_values = dict(
        field_name='newname', applicable_type='defect',
        applicable_predicate='pri:1', is_required=True, is_niche=True,
        is_multivalued=True, min_value=32, max_value=212, regex='a.*b',
        needs_member=True, needs_perm='EditIssue', grants_perm='DeleteIssue',
        notify_on='any_comment', docstring='new doc')
    self.SetUpUpdateFieldDef(1, new_values)

    self.mox.ReplayAll()
    new_values = new_values.copy()
    new_values['notify_on'] = 1
    self.config_service.UpdateFieldDef(
        self.cnxn, 789, 1, admin_ids=[], **new_values)
    self.mox.VerifyAll()

  ### Component definitions

  def SetUpFindMatchingComponentIDsAnyProject(self, _exact, rows):
    # TODO(jrobbins): more details here.
    self.config_service.componentdef_tbl.Select(
        self.cnxn, cols=['id'], where=mox.IsA(list)).AndReturn(rows)

  def testFindMatchingComponentIDsAnyProject_Rooted(self):
    self.SetUpFindMatchingComponentIDsAnyProject(True, [(1,), (2,), (3,)])

    self.mox.ReplayAll()
    comp_ids = self.config_service.FindMatchingComponentIDsAnyProject(
        self.cnxn, ['WindowManager', 'NetworkLayer'])
    self.mox.VerifyAll()
    self.assertItemsEqual([1, 2, 3], comp_ids)

  def testFindMatchingComponentIDsAnyProject_NonRooted(self):
    self.SetUpFindMatchingComponentIDsAnyProject(False, [(1,), (2,), (3,)])

    self.mox.ReplayAll()
    comp_ids = self.config_service.FindMatchingComponentIDsAnyProject(
        self.cnxn, ['WindowManager', 'NetworkLayer'], exact=False)
    self.mox.VerifyAll()
    self.assertItemsEqual([1, 2, 3], comp_ids)

  def SetUpCreateComponentDef(self, comp_id):
    self.config_service.componentdef_tbl.InsertRow(
        self.cnxn, project_id=789, path='WindowManager',
        docstring='doc', deprecated=False, commit=False,
        created=0, creator_id=0).AndReturn(comp_id)
    self.config_service.component2admin_tbl.InsertRows(
        self.cnxn, config_svc.COMPONENT2ADMIN_COLS, [], commit=False)
    self.config_service.component2cc_tbl.InsertRows(
        self.cnxn, config_svc.COMPONENT2CC_COLS, [], commit=False)
    self.config_service.component2label_tbl.InsertRows(
        self.cnxn, config_svc.COMPONENT2LABEL_COLS, [], commit=False)
    self.cnxn.Commit()

  def testCreateComponentDef(self):
    self.SetUpCreateComponentDef(1)

    self.mox.ReplayAll()
    comp_id = self.config_service.CreateComponentDef(
        self.cnxn, 789, 'WindowManager', 'doc', False, [], [], 0, 0, [])
    self.mox.VerifyAll()
    self.assertEqual(1, comp_id)

  def SetUpUpdateComponentDef(self, component_id):
    self.config_service.component2admin_tbl.Delete(
        self.cnxn, component_id=component_id, commit=False)
    self.config_service.component2admin_tbl.InsertRows(
        self.cnxn, config_svc.COMPONENT2ADMIN_COLS, [], commit=False)
    self.config_service.component2cc_tbl.Delete(
        self.cnxn, component_id=component_id, commit=False)
    self.config_service.component2cc_tbl.InsertRows(
        self.cnxn, config_svc.COMPONENT2CC_COLS, [], commit=False)
    self.config_service.component2label_tbl.Delete(
        self.cnxn, component_id=component_id, commit=False)
    self.config_service.component2label_tbl.InsertRows(
        self.cnxn, config_svc.COMPONENT2LABEL_COLS, [], commit=False)

    self.config_service.componentdef_tbl.Update(
        self.cnxn,
        {'path': 'DisplayManager', 'docstring': 'doc', 'deprecated': True},
        id=component_id, commit=False)
    self.cnxn.Commit()

  def testUpdateComponentDef(self):
    self.SetUpUpdateComponentDef(1)

    self.mox.ReplayAll()
    self.config_service.UpdateComponentDef(
        self.cnxn, 789, 1, path='DisplayManager', docstring='doc',
        deprecated=True, admin_ids=[], cc_ids=[], label_ids=[])
    self.mox.VerifyAll()

  def SetUpDeleteComponentDef(self, component_id):
    self.config_service.component2cc_tbl.Delete(
        self.cnxn, component_id=component_id, commit=False)
    self.config_service.component2admin_tbl.Delete(
        self.cnxn, component_id=component_id, commit=False)
    self.config_service.component2label_tbl.Delete(
        self.cnxn, component_id=component_id, commit=False)
    self.config_service.componentdef_tbl.Delete(
        self.cnxn, id=component_id, commit=False)
    self.cnxn.Commit()

  def testDeleteComponentDef(self):
    self.SetUpDeleteComponentDef(1)

    self.mox.ReplayAll()
    self.config_service.DeleteComponentDef(self.cnxn, 789, 1)
    self.mox.VerifyAll()

  ### Memcache management

  def testInvalidateMemcache(self):
    pass  # TODO(jrobbins): write this

  def testInvalidateMemcacheShards(self):
    NOW = 1234567
    memcache.set('789;1', NOW)
    memcache.set('789;2', NOW - 1000)
    memcache.set('789;3', NOW - 2000)
    memcache.set('all;1', NOW)
    memcache.set('all;2', NOW - 1000)
    memcache.set('all;3', NOW - 2000)

    # Delete some of them.
    self.config_service._InvalidateMemcacheShards(
        [(789, 1), (789, 2), (789,9)])

    self.assertIsNone(memcache.get('789;1'))
    self.assertIsNone(memcache.get('789;2'))
    self.assertEqual(NOW - 2000, memcache.get('789;3'))
    self.assertIsNone(memcache.get('all;1'))
    self.assertIsNone(memcache.get('all;2'))
    self.assertEqual(NOW - 2000, memcache.get('all;3'))

  def testInvalidateMemcacheForEntireProject(self):
    NOW = 1234567
    memcache.set('789;1', NOW)
    memcache.set('config:789', 'serialized config')
    memcache.set('label_rows:789', 'serialized label rows')
    memcache.set('status_rows:789', 'serialized status rows')
    memcache.set('field_rows:789', 'serialized field rows')
    memcache.set('890;1', NOW)  # Other projects will not be affected.

    self.config_service.InvalidateMemcacheForEntireProject(789)

    self.assertIsNone(memcache.get('789;1'))
    self.assertIsNone(memcache.get('config:789'))
    self.assertIsNone(memcache.get('status_rows:789'))
    self.assertIsNone(memcache.get('label_rows:789'))
    self.assertIsNone(memcache.get('field_rows:789'))
    self.assertEqual(NOW, memcache.get('890;1'))
