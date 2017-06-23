# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class Cache(object):
  """An interface to cache and retrieve data.

  Subclasses should implement the Get/Set functions.
  TODO: Add a Delete function (default to no-op) if needed later.
  """

  def Get(self, key):
    """Returns the cached data for the given key if available.

    Args:
      key (str): The key to identify the cached data.
    """
    raise NotImplementedError()

  def Set(self, key, data, expire_time=0):
    """Cache the given data which is identified by the given key.

    Args:
      key (str): The key to identify the cached data.
      data (object): The python object to be cached.
      expire_time (int): Number of seconds from current time (up to 1 month).
    """
    raise NotImplementedError()
