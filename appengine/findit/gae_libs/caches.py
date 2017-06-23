# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cStringIO
import pickle
import zlib

from google.appengine.api import memcache

from libs.cache import Cache


class PickledMemCache(Cache):
  """A memcache-backed implementation of the interface Cache.

  The data to be cached should be pickleable.
  Limitation: size of the pickled data and key should be <= 1MB.
  """

  def Get(self, key):
    return memcache.get(key)

  def Set(self, key, data, expire_time=0):
    return memcache.set(key, data, time=expire_time)


class _CachedItemMetaData(object):

  def __init__(self, number):
    self.number = number


class CompressedMemCache(Cache):
  """A memcache-backed implementation of the interface Cache with compression.

  The data to be cached will be pickled and then compressed.
  Data still > 1MB will be split into sub-piece and stored separately.
  During retrieval, if any sub-piece is missing, None is returned.
  """
  CHUNK_SIZE = 990000

  def Get(self, key):
    data = memcache.get(key)
    if isinstance(data, _CachedItemMetaData):
      num = data.number
      sub_keys = ['%s-%s' % (key, i) for i in range(num)]
      all_data = memcache.get_multi(sub_keys)
      if len(all_data) != num:  # Some data is missing.
        return None

      data_output = cStringIO.StringIO()
      for sub_key in sub_keys:
        data_output.write(all_data[sub_key])
      data = data_output.getvalue()

    return None if data is None else pickle.loads(zlib.decompress(data))

  def Set(self, key, data, expire_time=0):
    pickled_data = pickle.dumps(data)
    compressed_data = zlib.compress(pickled_data)

    all_data = {}
    if len(compressed_data) > self.CHUNK_SIZE:
      num = 0
      for index in xrange(0, len(compressed_data), self.CHUNK_SIZE):
        sub_key = '%s-%s' % (key, num)
        all_data[sub_key] = compressed_data[index:index + self.CHUNK_SIZE]
        num += 1

      all_data[key] = _CachedItemMetaData(num)
    else:
      all_data[key] = compressed_data

    keys_not_set = memcache.set_multi(all_data, time=expire_time)
    return len(keys_not_set) == 0
