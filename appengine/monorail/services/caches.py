# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes to manage cached values.

Monorail makes full use of the RAM of GAE frontends to reduce latency
and load on the database.
"""

import logging

from protorpc import protobuf

from google.appengine.api import memcache

from framework import framework_constants


INVALIDATE_KIND_VALUES = ['user', 'project', 'issue', 'issue_id', 'hotlist']
DEFAULT_MAX_SIZE = 10000


class RamCache(object):
  """An in-RAM cache with distributed invalidation."""

  def __init__(self, cache_manager, kind, max_size=None):
    assert kind in INVALIDATE_KIND_VALUES
    self.cache_manager = cache_manager
    self.kind = kind
    self.cache = {}
    self.max_size = max_size or DEFAULT_MAX_SIZE

  def CacheItem(self, key, item):
    """Store item at key in this cache, discarding a random item if needed."""
    if len(self.cache) >= self.max_size:
      self.cache.popitem()

    self.cache[key] = item

  def CacheAll(self, new_item_dict):
    """Cache all items in the given dict, dropping old items if needed."""
    if len(new_item_dict) >= self.max_size:
      logging.warn('Dumping the entire cache! %s', self.kind)
      self.cache = {}
    else:
      while len(self.cache) + len(new_item_dict) > self.max_size:
        self.cache.popitem()

    self.cache.update(new_item_dict)

  def GetItem(self, key):
    """Return the cached item if present, otherwise None."""
    return self.cache.get(key)

  def HasItem(self, key):
    """Return True if there is a value cached at the given key."""
    return key in self.cache

  def GetAll(self, keys):
    """Look up the given keys.

    Args:
      keys: a list of cache keys to look up.

    Returns:
      A pair: (hits_dict, misses_list) where hits_dict is a dictionary of
      all the given keys and the values that were found in the cache, and
      misses_list is a list of given keys that were not in the cache.
    """
    hits, misses = {}, []
    for key in keys:
      try:
        hits[key] = self.cache[key]
      except KeyError:
        misses.append(key)

    return hits, misses

  def LocalInvalidate(self, key):
    """Drop the given key from this cache, without distributed notification."""
    if key in self.cache:
      logging.info('Locally invalidating %r in kind=%r', key, self.kind)
    else:
      logging.info('Did not have %r in kind=%r in RAM', key, self.kind)
    self.cache.pop(key, None)

  def Invalidate(self, cnxn, key):
    """Drop key locally, and append it to the Invalidate DB table."""
    self.InvalidateKeys(cnxn, [key])

  def InvalidateKeys(self, cnxn, keys):
    """Drop keys locally, and append them to the Invalidate DB table."""
    for key in keys:
      self.LocalInvalidate(key)
    if self.cache_manager:
      self.cache_manager.StoreInvalidateRows(cnxn, self.kind, keys)

  def LocalInvalidateAll(self):
    """Invalidate all keys locally: just start over with an empty dict."""
    logging.info('Locally invalidating all in kind=%r', self.kind)
    self.cache = {}

  def InvalidateAll(self, cnxn):
    """Invalidate all keys in this cache."""
    self.LocalInvalidateAll()
    if self.cache_manager:
      self.cache_manager.StoreInvalidateAll(cnxn, self.kind)


class ValueCentricRamCache(RamCache):
  """Specialized version of RamCache that stores values in InvalidateTable.

  This is useful for caches that have non integer keys.
  """

  def LocalInvalidate(self, value):
    """Use the specified value to drop entries from the local cache."""
    keys_to_drop = []
    # Loop through and collect all keys with the specified value.
    for k, v in self.cache.iteritems():
      if v == value:
        keys_to_drop.append(k)
    for k in keys_to_drop:
      self.cache.pop(k, None)

  def InvalidateKeys(self, cnxn, keys):
    """Drop keys locally, and append their values to the Invalidate DB table."""
    # Find values to invalidate.
    values = [self.cache[key] for key in keys if self.cache.has_key(key)]
    if len(values) == len(keys):
      for value in values:
        self.LocalInvalidate(value)
      if self.cache_manager:
        self.cache_manager.StoreInvalidateRows(cnxn, self.kind, values)
    else:
      # If a value is not found in the cache then invalidate the whole cache.
      # This is done to ensure that we are not in an inconsistent state or in a
      # race condition.
      self.InvalidateAll(cnxn)


class AbstractTwoLevelCache(object):
  """A class to manage both RAM and memcache to retrieve objects.

  Subclasses must implement the FetchItems() method to get objects from
  the database when both caches miss.
  """

  # When loading a huge number of issues from the database, do it in chunks
  # so as to avoid timeouts.
  _FETCH_BATCH_SIZE = 10000

  def __init__(
      self, cache_manager, kind, memcache_prefix, pb_class, max_size=None,
      use_value_centric_cache=False):
    self.cache = cache_manager.MakeCache(
        kind, max_size=max_size,
        use_value_centric_cache=use_value_centric_cache)
    self.memcache_prefix = memcache_prefix
    self.pb_class = pb_class

  def CacheItem(self, key, value):
    """Add the given key-value pair to RAM and memcache."""
    self.cache.CacheItem(key, value)
    self._WriteToMemcache({key: value})

  def HasItem(self, key):
    """Return True if the given key is in the RAM cache."""
    return self.cache.HasItem(key)

  def GetAnyOnHandItem(self, keys, start=None, end=None):
    """Try to find one of the specified items in RAM."""
    if start is None:
      start = 0
    if end is None:
      end = len(keys)
    for i in xrange(start, end):
      key = keys[i]
      if self.cache.HasItem(key):
        return self.cache.GetItem(key)

    # Note: We could check memcache here too, but the round-trips to memcache
    # are kind of slow.  And, getting too many hits from memcache actually
    # fills our RAM cache too quickly and could lead to thrashing.

    return None

  def GetAll(self, cnxn, keys, use_cache=True, **kwargs):
    """Get values for the given keys from RAM, memcache, or the DB.

    Args:
      cnxn: connection to the database.
      keys: list of integer keys to look up.
      use_cache: set to False to always hit the database.
      **kwargs: any additional keywords are passed to FetchItems().

    Returns:
      A pair: hits, misses.  Where hits is {key: value} and misses is
      a list of any keys that were not found anywhere.
    """
    if use_cache:
      result_dict, missed_keys = self.cache.GetAll(keys)
    else:
      result_dict, missed_keys = {}, list(keys)

    if missed_keys and use_cache:
      memcache_hits, missed_keys = self._ReadFromMemcache(missed_keys)
      result_dict.update(memcache_hits)
      self.cache.CacheAll(memcache_hits)

    while missed_keys:
      missed_batch = missed_keys[:self._FETCH_BATCH_SIZE]
      missed_keys = missed_keys[self._FETCH_BATCH_SIZE:]
      retrieved_dict = self.FetchItems(cnxn, missed_batch, **kwargs)
      result_dict.update(retrieved_dict)
      if use_cache:
        self.cache.CacheAll(retrieved_dict)
        self._WriteToMemcache(retrieved_dict)

    still_missing_keys = [key for key in keys if key not in result_dict]
    return result_dict, still_missing_keys

  def _ReadFromMemcache(self, keys):
    """Read the given keys from memcache, return {key: value}, missing_keys."""
    memcache_hits = {}
    cached_dict = memcache.get_multi(
        [self._KeyToStr(key) for key in keys], key_prefix=self.memcache_prefix)

    for key_str, serialized_value in cached_dict.iteritems():
      value = self._StrToValue(serialized_value)
      key = self._StrToKey(key_str)
      if self._CheckCompatibility(value):
        memcache_hits[key] = value
        self.cache.CacheItem(key, value)

    still_missing_keys = [key for key in keys if key not in memcache_hits]
    logging.info(
        'decoded %d values from memcache %s, missing %d',
        len(memcache_hits), self.memcache_prefix, len(still_missing_keys))
    logging.info('_ReadFromMemcache got %r', memcache_hits)
    return memcache_hits, still_missing_keys

  # pylint: disable=unused-argument
  def _CheckCompatibility(self, value):
    """Subclasses can check if value is usable by the current app version."""
    return True

  def _WriteToMemcache(self, retrieved_dict):
    """Write entries for each key-value pair to memcache.  Encode PBs."""
    strs_to_cache = {
        self._KeyToStr(key): self._ValueToStr(value)
        for key, value in retrieved_dict.iteritems()}
    memcache.add_multi(
        strs_to_cache, key_prefix=self.memcache_prefix,
        time=framework_constants.MEMCACHE_EXPIRATION)
    logging.info('cached batch of %d values in memcache %s',
                 len(retrieved_dict), self.memcache_prefix)
    logging.info('_WriteToMemcache wrote %r', retrieved_dict)

  def _KeyToStr(self, key):
    """Convert our int IDs to strings for use as memcache keys."""
    return str(key)

  def _StrToKey(self, key_str):
    """Convert memcache keys back to the ints that we use as IDs."""
    return int(key_str)

  def _ValueToStr(self, value):
    """Serialize an application object so that it can be stored in memcache."""
    if not self.pb_class:
      return value
    elif self.pb_class == int:
      return str(value)
    else:
      return protobuf.encode_message(value)

  def _StrToValue(self, serialized_value):
    """Deserialize an application object that was stored in memcache."""
    if not self.pb_class:
      return serialized_value
    elif self.pb_class == int:
      return int(serialized_value)
    else:
      return protobuf.decode_message(self.pb_class, serialized_value)

  def InvalidateKeys(self, cnxn, keys):
    """Drop the given keys from both RAM and memcache."""
    self.cache.InvalidateKeys(cnxn, keys)
    memcache.delete_multi(
        [self._KeyToStr(key) for key in keys], seconds=5,
        key_prefix=self.memcache_prefix)

  def InvalidateAllKeys(self, cnxn, keys):
    """Drop the given keys from memcache and invalidate all keys in RAM.

    Useful for avoiding inserting many rows into the Invalidate table when
    invalidating a large group of keys all at once. Only use when necessary.
    """
    self.cache.InvalidateAll(cnxn)
    memcache.delete_multi(
        [self._KeyToStr(key) for key in keys], seconds=5,
        key_prefix=self.memcache_prefix)

  def GetAllAlreadyInRam(self, keys):
    """Look only in RAM to return {key: values}, missed_keys."""
    result_dict, missed_keys = self.cache.GetAll(keys)
    return result_dict, missed_keys

  def InvalidateAllRamEntries(self, cnxn):
    """Drop all RAM cache entries. It will refill as needed from memcache."""
    self.cache.InvalidateAll(cnxn)

  def FetchItems(self, cnxn, keys, **kwargs):
    """On RAM and memcache miss, hit the database."""
    raise NotImplementedError()
