# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno
import os
import pickle
import threading
import zlib

from libs.cache import Cache


PREDATOR_DIR = os.path.join(os.path.dirname(__file__), os.path.pardir, 'crash')
CACHE_DIR = os.path.join(PREDATOR_DIR, '.predator', 'cache')


class LocalCache(Cache):
  """Cacher that uses local files to cache data."""
  lock = threading.Lock()

  def __init__(self, cache_dir=None):
    self._cache_dir = cache_dir
    self._initialized = False

  @property
  def cache_dir(self):
    return self._cache_dir or CACHE_DIR

  def Get(self, key):
    with LocalCache.lock:
      path = os.path.join(self.cache_dir, key)
      if not os.path.exists(path):
        return None

      try:
        with open(path) as f:
          return pickle.loads(zlib.decompress(f.read()))
      except Exception as error:  # pragma: no cover.
        raise Exception('Failed loading cache: %s' % error)

  def Set(self, key, data, expire_time=0):  # pylint: disable=W
    with LocalCache.lock:
      try:
        if not self._initialized:  # pragma: no cover.
          try:
            os.makedirs(self.cache_dir)
          except OSError as exc:
            if exc.errno != errno.EEXIST:
              raise
          self._initialized = True
        with open(os.path.join(self.cache_dir, key), 'wb') as f:
          f.write(zlib.compress(pickle.dumps(data)))
      except Exception as e:  # pragma: no cover.
        raise Exception('Failed setting cache for key %s: %s' % (key, e))
