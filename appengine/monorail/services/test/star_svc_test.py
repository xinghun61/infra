# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the star service."""

import unittest

import mox

from google.appengine.ext import testbed

import settings
from framework import sql
from proto import user_pb2
from services import star_svc
from testing import fake


class AbstractStarServiceTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.mox = mox.Mox()
    self.mock_tbl = self.mox.CreateMock(sql.SQLTableManager)
    self.cnxn = 'fake connection'
    self.cache_manager = fake.CacheManager()
    self.star_service = star_svc.AbstractStarService(
        self.cache_manager, self.mock_tbl, 'item_id', 'user_id', 'project')

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def SetUpExpungeStars(self):
    self.mock_tbl.Delete(self.cnxn, item_id=123)

  def testExpungeStars(self):
    self.SetUpExpungeStars()
    self.mox.ReplayAll()
    self.star_service.ExpungeStars(self.cnxn, 123)
    self.mox.VerifyAll()

  def SetUpLookupItemsStarrers(self):
    self.mock_tbl.Select(
        self.cnxn, cols=['item_id', 'user_id'],
        item_id=[234]).AndReturn([(234, 111L), (234, 222L)])

  def testLookupItemsStarrers(self):
    self.star_service.starrer_cache.CacheItem(123, [111L, 333L])
    self.SetUpLookupItemsStarrers()
    self.mox.ReplayAll()
    starrer_list_dict = self.star_service.LookupItemsStarrers(
        self.cnxn, [123, 234])
    self.mox.VerifyAll()
    self.assertItemsEqual([123, 234], starrer_list_dict.keys())
    self.assertItemsEqual([111L, 333L], starrer_list_dict[123])
    self.assertItemsEqual([111L, 222L], starrer_list_dict[234])
    self.assertItemsEqual([111L, 333L],
                          self.star_service.starrer_cache.GetItem(123))
    self.assertItemsEqual([111L, 222L],
                          self.star_service.starrer_cache.GetItem(234))

  def SetUpLookupStarredItemIDs(self):
    self.mock_tbl.Select(
        self.cnxn, cols=['item_id'], user_id=111L).AndReturn(
            [(123,), (234,)])

  def testLookupStarredItemIDs(self):
    self.SetUpLookupStarredItemIDs()
    self.mox.ReplayAll()
    item_ids = self.star_service.LookupStarredItemIDs(self.cnxn, 111L)
    self.mox.VerifyAll()
    self.assertItemsEqual([123, 234], item_ids)
    self.assertItemsEqual([123, 234],
                          self.star_service.star_cache.GetItem(111L))

  def testIsItemStarredBy(self):
    self.SetUpLookupStarredItemIDs()
    self.mox.ReplayAll()
    self.assertTrue(self.star_service.IsItemStarredBy(self.cnxn, 123, 111L))
    self.assertTrue(self.star_service.IsItemStarredBy(self.cnxn, 234, 111))
    self.assertFalse(
        self.star_service.IsItemStarredBy(self.cnxn, 435, 111L))
    self.mox.VerifyAll()

  def SetUpCountItemStars(self):
    self.mock_tbl.Select(
        self.cnxn, cols=['item_id', 'COUNT(user_id)'], item_id=[234],
        group_by=['item_id']).AndReturn([(234, 2)])

  def testCountItemStars(self):
    self.star_service.star_count_cache.CacheItem(123, 3)
    self.SetUpCountItemStars()
    self.mox.ReplayAll()
    self.assertEqual(3, self.star_service.CountItemStars(self.cnxn, 123))
    self.assertEqual(2, self.star_service.CountItemStars(self.cnxn, 234))
    self.mox.VerifyAll()

  def testCountItemsStars(self):
    self.star_service.star_count_cache.CacheItem(123, 3)
    self.SetUpCountItemStars()
    self.mox.ReplayAll()
    count_dict = self.star_service.CountItemsStars(
        self.cnxn, [123, 234])
    self.mox.VerifyAll()
    self.assertItemsEqual([123, 234], count_dict.keys())
    self.assertEqual(3, count_dict[123])
    self.assertEqual(2, count_dict[234])

  def SetUpSetStar_Add(self):
    self.mock_tbl.InsertRows(
        self.cnxn, ['item_id', 'user_id'], [(123, 111L)], ignore=True)

  def testSetStar_Add(self):
    self.SetUpSetStar_Add()
    self.mox.ReplayAll()
    self.star_service.SetStar(self.cnxn, 123, 111L, True)
    self.mox.VerifyAll()
    self.assertFalse(self.star_service.star_cache.HasItem(123))
    self.assertFalse(self.star_service.starrer_cache.HasItem(123))
    self.assertFalse(self.star_service.star_count_cache.HasItem(123))

  def SetUpSetStar_Remove(self):
    self.mock_tbl.Delete(self.cnxn, item_id=123, user_id=[111L])

  def testSetStar_Remove(self):
    self.SetUpSetStar_Remove()
    self.mox.ReplayAll()
    self.star_service.SetStar(self.cnxn, 123, 111L, False)
    self.mox.VerifyAll()
    self.assertFalse(self.star_service.star_cache.HasItem(123))
    self.assertFalse(self.star_service.starrer_cache.HasItem(123))
    self.assertFalse(self.star_service.star_count_cache.HasItem(123))

  def SetUpSetStarsBatch_Add(self):
    self.mock_tbl.InsertRows(
        self.cnxn, ['item_id', 'user_id'], [(123, 111L), (123, 222L)],
        ignore=True)

  def testSetStarsBatch_Add(self):
    self.SetUpSetStarsBatch_Add()
    self.mox.ReplayAll()
    self.star_service.SetStarsBatch(self.cnxn, 123, [111L, 222L], True)
    self.mox.VerifyAll()
    self.assertFalse(self.star_service.star_cache.HasItem(123))
    self.assertFalse(self.star_service.starrer_cache.HasItem(123))
    self.assertFalse(self.star_service.star_count_cache.HasItem(123))

  def SetUpSetStarsBatch_Remove(self):
    self.mock_tbl.Delete(self.cnxn, item_id=123, user_id=[111L, 222L])

  def testSetStarsBatch_Remove(self):
    self.SetUpSetStarsBatch_Remove()
    self.mox.ReplayAll()
    self.star_service.SetStarsBatch(self.cnxn, 123, [111L, 222L], False)
    self.mox.VerifyAll()
    self.assertFalse(self.star_service.star_cache.HasItem(123))
    self.assertFalse(self.star_service.starrer_cache.HasItem(123))
    self.assertFalse(self.star_service.star_count_cache.HasItem(123))
