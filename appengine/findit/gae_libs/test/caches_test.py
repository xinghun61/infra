# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import pickle
import zlib

from google.appengine.api import memcache

from testing_utils import testing

from gae_libs import caches


class CachesTest(testing.AppengineTestCase):

  def testPickledMemCache(self):
    """Tests using app engine ``memcache`` to cache data."""
    cache = caches.PickledMemCache()
    cache.Set('a', 'd')
    self.assertEquals('d', cache.Get('a'))

  def _MockPickleAndZlib(self):

    def Func(string, *_, **__):
      return string

    self.mock(pickle, 'dumps', Func)
    self.mock(pickle, 'loads', Func)
    self.mock(zlib, 'compress', Func)
    self.mock(zlib, 'decompress', Func)

  def testCachingSmallDataInCompressedMemCache(self):
    """Tests if ``CompressedMemCache`` caches small data (1KB) successfully."""
    self._MockPickleAndZlib()
    cache = caches.CompressedMemCache()
    data = 'A' * 1024  # A string of size 1KB.
    cache.Set('a', data)
    self.assertEquals(data, cache.Get('a'))

  def testCachingLargeDataInCompressedMemCache(self):
    """Tests if LargData are cached successfully.

    App engine memcache can only cache data < 1MB at one time, so data > 1MB
    will be split into sub-piece and stored separately.
    """
    self._MockPickleAndZlib()
    cache = caches.CompressedMemCache()
    data = 'A' * (1024 * 1024 * 2)  # A string of size 2MB.
    cache.Set('a', data)
    self.assertEquals(data, cache.Get('a'))

  def testMissingSubPieceOfLargeDataInCompressedMemCache(self):
    """Tests ``CompressedMemCache`` returns None when the data is broken."""
    self._MockPickleAndZlib()
    cache = caches.CompressedMemCache()
    data = 'A' * (1024 * 1024 * 2)  # A string of size 2MB.
    cache.Set('a', data)
    memcache.delete('a-0')
    self.assertEquals(None, cache.Get('a'))
