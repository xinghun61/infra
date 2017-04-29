# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import __builtin__
import mock
import os
import pickle
import zlib

from testing_utils import testing

from local_libs import local_cache


class LocalCacheTest(testing.AppengineTestCase):

  def testLocalCache(self):
    fake_dir = 'fake_dir'
    cacher = local_cache.LocalCache(cache_dir=fake_dir)
    def _MockPathExists(path, *_):
      return False if path == os.path.join(
          fake_dir, 'uncached_key') else True
    self.mock(os.path, 'exists', _MockPathExists)

    value = 'val'
    with mock.patch('__builtin__.open', mock.mock_open(
        read_data=zlib.compress(pickle.dumps(value)))) as m:
      cacher.Set('a', 'b')
      m.assert_called_once_with(os.path.join(fake_dir, 'a'), 'wb')
      self.assertEqual(value, cacher.Get('key'))
      self.assertIsNone(cacher.Get('uncached_key'))
