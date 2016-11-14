# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import pickle
import threading
import zlib

from lib.cache_decorator import Cacher

CACHE_DIR = os.path.join(os.path.expanduser('~'), '.predator', 'cache')


class LocalCacher(Cacher):
  """Cacher that uses local files to cache data."""
  lock = threading.Lock()

  def __init__(self, cache_dir=CACHE_DIR):
    self.cache_dir = cache_dir
    with LocalCacher.lock:
      if not os.path.exists(cache_dir): # pragma: no cover.
        os.makedirs(cache_dir)

  def Get(self, key):
    with LocalCacher.lock:
      path = os.path.join(self.cache_dir, key)
      if not os.path.exists(path):
        return None

      try:
        with open(path) as f:
          return pickle.loads(zlib.decompress(f.read()))
      except Exception as error:  # pragma: no cover.
        logging.exception('Failed loading cache: %s', error)
        return None

  def Set(self, key, data, expire_time=0):  # pylint: disable=W
    with LocalCacher.lock:
      try:
        with open(os.path.join(self.cache_dir, key), 'wb') as f:
          f.write(zlib.compress(pickle.dumps(data)))
      except Exception as e:  # pragma: no cover.
        logging.exception('Failed setting cache for key %s: %s', key, e)
