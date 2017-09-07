# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the cachemanager service."""

import unittest

import mox

from framework import sql
from services import cachemanager_svc
from services import caches
from services import service_manager
from testing import fake
from testing import testing_helpers


class CacheManagerServiceTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = fake.MonorailConnection()
    self.cache_manager = cachemanager_svc.CacheManager()
    self.cache_manager.invalidate_tbl = self.mox.CreateMock(
        sql.SQLTableManager)

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testRegisterCache(self):
    ram_cache = 'fake ramcache'
    self.cache_manager.RegisterCache(ram_cache, 'issue')
    self.assertTrue(ram_cache in self.cache_manager.cache_registry['issue'])

  def testRegisterCache_UnknownKind(self):
    ram_cache = 'fake ramcache'
    self.assertRaises(
      AssertionError,
      self.cache_manager.RegisterCache, ram_cache, 'foo')

  def testProcessInvalidateRows_Empty(self):
    rows = []
    self.cache_manager._ProcessInvalidationRows(rows)
    self.assertEqual(0, self.cache_manager.processed_invalidations_up_to)

  def testProcessInvalidateRows_Some(self):
    ram_cache = caches.RamCache(self.cache_manager, 'issue')
    ram_cache.CacheAll({
        33: 'issue 33',
        34: 'issue 34',
        })
    rows = [(1, 'issue', 34),
            (2, 'project', 789),
            (3, 'issue', 39)]
    self.cache_manager._ProcessInvalidationRows(rows)
    self.assertEqual(3, self.cache_manager.processed_invalidations_up_to)
    self.assertTrue(ram_cache.HasItem(33))
    self.assertFalse(ram_cache.HasItem(34))

  def testProcessInvalidateRows_All(self):
    ram_cache = caches.RamCache(self.cache_manager, 'issue')
    ram_cache.CacheAll({
        33: 'issue 33',
        34: 'issue 34',
        })
    rows = [(991, 'issue', 34),
            (992, 'project', 789),
            (993, 'issue', cachemanager_svc.INVALIDATE_ALL_KEYS)]
    self.cache_manager._ProcessInvalidationRows(rows)
    self.assertEqual(993, self.cache_manager.processed_invalidations_up_to)
    self.assertEqual({}, ram_cache.cache)

  def SetUpDoDistributedInvalidation(self, rows):
    self.cache_manager.invalidate_tbl.Select(
        self.cnxn, cols=['timestep', 'kind', 'cache_key'],
        where=[('timestep > %s', [0])],
        order_by=[('timestep DESC', [])],
        limit=cachemanager_svc.MAX_INVALIDATE_ROWS_TO_CONSIDER
        ).AndReturn(rows)

  def testDoDistributedInvalidation_Empty(self):
    rows = []
    self.SetUpDoDistributedInvalidation(rows)
    self.mox.ReplayAll()
    self.cache_manager.DoDistributedInvalidation(self.cnxn)
    self.mox.VerifyAll()
    self.assertEqual(0, self.cache_manager.processed_invalidations_up_to)

  def testDoDistributedInvalidation_Some(self):
    ram_cache = caches.RamCache(self.cache_manager, 'issue')
    ram_cache.CacheAll({
        33: 'issue 33',
        34: 'issue 34',
        })
    rows = [(1, 'issue', 34),
            (2, 'project', 789),
            (3, 'issue', 39)]
    self.SetUpDoDistributedInvalidation(rows)
    self.mox.ReplayAll()
    self.cache_manager.DoDistributedInvalidation(self.cnxn)
    self.mox.VerifyAll()
    self.assertEqual(3, self.cache_manager.processed_invalidations_up_to)
    self.assertTrue(ram_cache.HasItem(33))
    self.assertFalse(ram_cache.HasItem(34))

  def testDoDistributedInvalidation_Redundant(self):
    ram_cache = caches.RamCache(self.cache_manager, 'issue')
    ram_cache.CacheAll({
        33: 'issue 33',
        34: 'issue 34',
        })
    rows = [(1, 'issue', 34),
            (2, 'project', 789),
            (3, 'issue', 39),
            (4, 'project', 789),
            (5, 'issue', 39)]
    self.SetUpDoDistributedInvalidation(rows)
    self.mox.ReplayAll()
    self.cache_manager.DoDistributedInvalidation(self.cnxn)
    self.mox.VerifyAll()
    self.assertEqual(5, self.cache_manager.processed_invalidations_up_to)
    self.assertTrue(ram_cache.HasItem(33))
    self.assertFalse(ram_cache.HasItem(34))

  def testStoreInvalidateRows_UnknownKind(self):
    self.assertRaises(
        AssertionError,
        self.cache_manager.StoreInvalidateRows, self.cnxn, 'foo', [1, 2])

  def SetUpStoreInvalidateRows(self, rows):
    self.cache_manager.invalidate_tbl.InsertRows(
        self.cnxn, ['kind', 'cache_key'], rows)

  def testStoreInvalidateRows(self):
    rows = [('issue', 1), ('issue', 2)]
    self.SetUpStoreInvalidateRows(rows)
    self.mox.ReplayAll()
    self.cache_manager.StoreInvalidateRows(self.cnxn, 'issue', [1, 2])
    self.mox.VerifyAll()

  def SetUpStoreInvalidateAll(self, kind):
    self.cache_manager.invalidate_tbl.InsertRow(
        self.cnxn, kind=kind, cache_key=cachemanager_svc.INVALIDATE_ALL_KEYS,
        ).AndReturn(44)
    self.cache_manager.invalidate_tbl.Delete(
        self.cnxn, kind=kind, where=[('timestep < %s', [44])])

  def testStoreInvalidateAll(self):
    self.SetUpStoreInvalidateAll('issue')
    self.mox.ReplayAll()
    self.cache_manager.StoreInvalidateAll(self.cnxn, 'issue')
    self.mox.VerifyAll()


class RamCacheConsolidateTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = 'fake connection'
    self.cache_manager = cachemanager_svc.CacheManager()
    self.cache_manager.invalidate_tbl = self.mox.CreateMock(
        sql.SQLTableManager)
    self.services = service_manager.Services(
        cache_manager=self.cache_manager)
    self.servlet = cachemanager_svc.RamCacheConsolidate(
        'req', 'res', services=self.services)

  def testHandleRequest_NothingToDo(self):
    mr = testing_helpers.MakeMonorailRequest()
    self.cache_manager.invalidate_tbl.SelectValue(
        mr.cnxn, 'COUNT(*)').AndReturn(112)
    self.cache_manager.invalidate_tbl.SelectValue(
        mr.cnxn, 'COUNT(*)').AndReturn(112)  
    self.mox.ReplayAll()

    json_data = self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()
    self.assertEqual(json_data['old_count'], 112)
    self.assertEqual(json_data['new_count'], 112)

  def testHandleRequest_Truncate(self):
    mr = testing_helpers.MakeMonorailRequest()
    self.cache_manager.invalidate_tbl.SelectValue(
        mr.cnxn, 'COUNT(*)').AndReturn(4012)
    self.cache_manager.invalidate_tbl.Select(
        mr.cnxn, ['timestep'],
        order_by=[('timestep DESC', [])],
        limit=cachemanager_svc.MAX_INVALIDATE_ROWS_TO_CONSIDER
        ).AndReturn([[3012]])  # Actual would be 1000 rows ending with 3012.
    self.cache_manager.invalidate_tbl.Delete(
        mr.cnxn, where=[('timestep < %s', [3012])])
    self.cache_manager.invalidate_tbl.SelectValue(
        mr.cnxn, 'COUNT(*)').AndReturn(1000)
    self.mox.ReplayAll()

    json_data = self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()
    self.assertEqual(json_data['old_count'], 4012)
    self.assertEqual(json_data['new_count'], 1000)
