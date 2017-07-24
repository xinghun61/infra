# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the cache classes."""

import unittest

from google.appengine.api import memcache
from google.appengine.ext import testbed

from services import caches
from testing import fake


class RamCacheTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake connection'
    self.cache_manager = fake.CacheManager()
    self.ram_cache = caches.RamCache(self.cache_manager, 'issue', max_size=3)

  def testCacheItem(self):
    self.ram_cache.CacheItem(123, 'foo')
    self.assertEqual('foo', self.ram_cache.cache[123])

  def testCacheItem_DropsOldItems(self):
    self.ram_cache.CacheItem(123, 'foo')
    self.ram_cache.CacheItem(234, 'foo')
    self.ram_cache.CacheItem(345, 'foo')
    self.ram_cache.CacheItem(456, 'foo')
    # The cache does not get bigger than its limit.
    self.assertEqual(3, len(self.ram_cache.cache))
    # An old value is dropped, not the newly added one.
    self.assertIn(456, self.ram_cache.cache)

  def testCacheAll(self):
    self.ram_cache.CacheAll({123: 'foo'})
    self.assertEqual('foo', self.ram_cache.cache[123])

  def testCacheAll_DropsOldItems(self):
    self.ram_cache.CacheAll({1: 'a', 2: 'b', 3: 'c'})
    self.ram_cache.CacheAll({4: 'x', 5: 'y'})
    # The cache does not get bigger than its limit.
    self.assertEqual(3, len(self.ram_cache.cache))
    # An old value is dropped, not the newly added one.
    self.assertIn(4, self.ram_cache.cache)
    self.assertIn(5, self.ram_cache.cache)
    self.assertEqual('y', self.ram_cache.cache[5])

  def testHasItem(self):
    self.ram_cache.CacheItem(123, 'foo')
    self.assertTrue(self.ram_cache.HasItem(123))
    self.assertFalse(self.ram_cache.HasItem(999))

  def testGetAll(self):
    self.ram_cache.CacheItem(123, 'foo')
    self.ram_cache.CacheItem(124, 'bar')
    hits, misses = self.ram_cache.GetAll([123, 124, 999])
    self.assertEqual({123: 'foo', 124: 'bar'}, hits)
    self.assertEqual([999], misses)

  def testLocalInvalidate(self):
    self.ram_cache.CacheAll({123: 'a', 124: 'b', 125: 'c'})
    self.ram_cache.LocalInvalidate(124)
    self.assertEqual(2, len(self.ram_cache.cache))
    self.assertNotIn(124, self.ram_cache.cache)

    self.ram_cache.LocalInvalidate(999)
    self.assertEqual(2, len(self.ram_cache.cache))

  def testInvalidateKeys(self):
    self.ram_cache.CacheAll({123: 'a', 124: 'b', 125: 'c'})
    self.ram_cache.InvalidateKeys(self.cnxn, [124])
    self.assertEqual(2, len(self.ram_cache.cache))
    self.assertNotIn(124, self.ram_cache.cache)
    self.assertEqual(self.cache_manager.last_call,
                     ('StoreInvalidateRows', self.cnxn, 'issue', [124]))

  def testLocalInvalidateAll(self):
    self.ram_cache.CacheAll({123: 'a', 124: 'b', 125: 'c'})
    self.ram_cache.LocalInvalidateAll()
    self.assertEqual(0, len(self.ram_cache.cache))

  def testInvalidateAll(self):
    self.ram_cache.CacheAll({123: 'a', 124: 'b', 125: 'c'})
    self.ram_cache.InvalidateAll(self.cnxn)
    self.assertEqual(0, len(self.ram_cache.cache))
    self.assertEqual(self.cache_manager.last_call,
                     ('StoreInvalidateAll', self.cnxn, 'issue'))


class TestableTwoLevelCache(caches.AbstractTwoLevelCache):

  def __init__(self, cache_manager, kind, max_size=None):
    super(TestableTwoLevelCache, self).__init__(
        cache_manager, kind, 'testable:', None, max_size=max_size)

  # pylint: disable=unused-argument
  def FetchItems(self, cnxn, keys, **kwargs):
    """On RAM and memcache miss, hit the database."""
    return {key: key for key in keys if key < 900}


class AbstractTwoLevelCacheTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.cnxn = 'fake connection'
    self.cache_manager = fake.CacheManager()
    self.testable_cache = TestableTwoLevelCache(self.cache_manager, 'issue')

  def tearDown(self):
    self.testbed.deactivate()

  def testCacheItem(self):
    self.testable_cache.CacheItem(123, 12300)
    self.assertEqual(12300, self.testable_cache.cache.cache[123])

  def testHasItem(self):
    self.testable_cache.CacheItem(123, 12300)
    self.assertTrue(self.testable_cache.HasItem(123))
    self.assertFalse(self.testable_cache.HasItem(444))
    self.assertFalse(self.testable_cache.HasItem(999))

  def testGetAll_FetchGetsItFromMemcache(self):
    self.testable_cache.CacheItem(123, 12300)
    self.testable_cache.CacheItem(124, 12400)
    # Clear the RAM cache so that we find items in memcache.
    self.testable_cache.cache.LocalInvalidateAll()
    self.testable_cache.CacheItem(125, 12500)
    hits, misses = self.testable_cache.GetAll(
        self.cnxn, [123, 124, 333, 444])
    self.assertEqual({123: 12300, 124: 12400, 333: 333, 444: 444}, hits)
    self.assertEqual([], misses)
    # The RAM cache now has items found in memcache and DB.
    self.assertItemsEqual(
        [123, 124, 125, 333, 444],
        self.testable_cache.cache.cache.keys())

  def testGetAll_FetchGetsItFromDB(self):
    self.testable_cache.CacheItem(123, 12300)
    self.testable_cache.CacheItem(124, 12400)
    hits, misses = self.testable_cache.GetAll(
        self.cnxn, [123, 124, 333, 444])
    self.assertEqual({123: 12300, 124: 12400, 333: 333, 444: 444}, hits)
    self.assertEqual([], misses)

  def testGetAll_FetchDoesNotFindIt(self):
    self.testable_cache.CacheItem(123, 12300)
    self.testable_cache.CacheItem(124, 12400)
    hits, misses = self.testable_cache.GetAll(
        self.cnxn, [123, 124, 999])
    self.assertEqual({123: 12300, 124: 12400}, hits)
    self.assertEqual([999], misses)

  def testWriteToMemcache_Normal(self):
    retrieved_dict = {123: 12300, 124: 12400}
    self.testable_cache._WriteToMemcache(retrieved_dict)
    actual_123 = memcache.get('testable:123')
    self.assertEqual(12300, actual_123)
    actual_124 = memcache.get('testable:124')
    self.assertEqual(12400, actual_124)

  def testWriteToMemcache_HugeValue(self):
    """If memcache refuses to store a huge value, we don't store any."""
    self.testable_cache._WriteToMemcache({124: 124999})  # Gets deleted.

    huge_str = 'huge' * 260000
    retrieved_dict = {123: huge_str, 124: 12400}
    self.testable_cache._WriteToMemcache(retrieved_dict)
    actual_123 = memcache.get('testable:123')
    self.assertEqual(None, actual_123)
    actual_124 = memcache.get('testable:124')
    self.assertEqual(None, actual_124)

  def testInvalidateKeys(self):
    self.testable_cache.CacheItem(123, 12300)
    self.testable_cache.CacheItem(124, 12400)
    self.testable_cache.CacheItem(125, 12500)
    self.testable_cache.InvalidateKeys(self.cnxn, [124])
    self.assertEqual(2, len(self.testable_cache.cache.cache))
    self.assertNotIn(124, self.testable_cache.cache.cache)
    self.assertEqual(self.cache_manager.last_call,
                     ('StoreInvalidateRows', self.cnxn, 'issue', [124]))

  def testGetAllAlreadyInRam(self):
    self.testable_cache.CacheItem(123, 12300)
    self.testable_cache.CacheItem(124, 12400)
    hits, misses = self.testable_cache.GetAllAlreadyInRam(
        [123, 124, 333, 444, 999])
    self.assertEqual({123: 12300, 124: 12400}, hits)
    self.assertEqual([333, 444, 999], misses)

  def testInvalidateAllRamEntries(self):
    self.testable_cache.CacheItem(123, 12300)
    self.testable_cache.CacheItem(124, 12400)
    self.testable_cache.InvalidateAllRamEntries(self.cnxn)
    self.assertFalse(self.testable_cache.HasItem(123))
    self.assertFalse(self.testable_cache.HasItem(124))
