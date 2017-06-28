# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A simple in-RAM cache with distributed invalidation.

Here's how it works:
 + Each frontend or backend job has one CacheManager which
   owns a set of RamCache objects, which are basically dictionaries.
 + Each job can put objects in its own local cache, and retrieve them.
 + When an item is modified, the item at the corresponding cache key
   is invalidated, which means two things: (a) it is dropped from the
   local RAM cache, and (b) the key is written to the Invalidate table.
 + On each incoming request, the job checks the Invalidate table for
   any entries added since the last time that it checked.  If it finds
   any, it drops all RamCache entries for the corresponding key.
 + There is also a cron task that truncates old Invalidate entries
   when the table is too large.  If a frontend job sees more than the
   max Invalidate rows, it will drop everything from all caches,
   because it does not know what it missed due to truncation.
 + The special key 0 means to drop all cache entries.

This approach makes jobs use cached values that are not stale at the
time that processing of each request begins.  There is no guarantee that
an item will not be modified by some other job and that the cached entry
could become stale during the lifetime of that same request.

TODO(jrobbins): Listener hook so that client code can register its own
handler for invalidation events.  E.g., the sorting code has a cache that
is correctly invalidated on each issue change, but needs to be completely
dropped when a config is modified.

TODO(jrobbins): If this part of the system becomes a bottleneck, consider
some optimizations: (a) splitting the table into multiple tables by
kind, or (b) sharding the table by cache_key.  Or, maybe leverage memcache
to avoid even hitting the DB in the frequent case where nothing has changed.
"""

import collections
import logging

from framework import jsonfeed
from framework import sql
from services import caches


INVALIDATE_TABLE_NAME = 'Invalidate'
INVALIDATE_COLS = ['timestep', 'kind', 'cache_key']
INVALIDATE_ALL_KEYS = 0
MAX_INVALIDATE_ROWS_TO_CONSIDER = 1000


class CacheManager(object):
  """Service class to manage RAM caches and shared Invalidate table."""

  def __init__(self):
    self.cache_registry = collections.defaultdict(list)
    self.processed_invalidations_up_to = 0
    self.invalidate_tbl = sql.SQLTableManager(INVALIDATE_TABLE_NAME)

  def MakeCache(self, kind, max_size=None, use_value_centric_cache=False):
    """Make a new cache and register it for future invalidations."""
    if use_value_centric_cache:
      cache = caches.ValueCentricRamCache(self, kind, max_size=max_size)
    else:
      cache = caches.RamCache(self, kind, max_size=max_size)
    self.cache_registry[kind].append(cache)
    return cache

  def _InvalidateAllCaches(self):
    """Invalidate all cache entries."""
    for cache_list in self.cache_registry.values():
      for cache in cache_list:
        cache.LocalInvalidateAll()

  def _ProcessInvalidationRows(self, rows):
    """Invalidate cache entries indicated by database rows."""
    already_done = set()
    for timestep, kind, key in rows:
      self.processed_invalidations_up_to = max(
          self.processed_invalidations_up_to, timestep)
      if (kind, key) in already_done:
        continue
      already_done.add((kind, key))
      for cache in self.cache_registry[kind]:
        if key == INVALIDATE_ALL_KEYS:
          cache.LocalInvalidateAll()
        else:
          cache.LocalInvalidate(key)

  def DoDistributedInvalidation(self, cnxn):
    """Drop any cache entries that were invalidated by other jobs."""
    # Only consider a reasonable number of rows so that we can never
    # get bogged down on this step.  If there are too many rows to
    # process, just invalidate all caches, and process the last group
    # of rows to update processed_invalidations_up_to.
    rows = self.invalidate_tbl.Select(
        cnxn, cols=INVALIDATE_COLS,
        where=[('timestep > %s', [self.processed_invalidations_up_to])],
        order_by=[('timestep DESC', [])],
        limit=MAX_INVALIDATE_ROWS_TO_CONSIDER)

    cnxn.Commit()

    if len(rows) == MAX_INVALIDATE_ROWS_TO_CONSIDER:
      logging.info('Invaliditing all caches: there are too many invalidations')
      self._InvalidateAllCaches()

    logging.info('Saw %d invalidation rows', len(rows))
    self._ProcessInvalidationRows(rows)

  def StoreInvalidateRows(self, cnxn, kind, keys):
    """Store rows to let all jobs know to invalidate the given keys."""
    assert kind in caches.INVALIDATE_KIND_VALUES
    self.invalidate_tbl.InsertRows(
        cnxn, ['kind', 'cache_key'], [(kind, key) for key in keys])

  def StoreInvalidateAll(self, cnxn, kind):
    """Store a value to tell all jobs to invalidate all items of this kind."""
    last_timestep = self.invalidate_tbl.InsertRow(
        cnxn, kind=kind, cache_key=INVALIDATE_ALL_KEYS)
    self.invalidate_tbl.Delete(
        cnxn, kind=kind, where=[('timestep < %s', [last_timestep])])


class RamCacheConsolidate(jsonfeed.InternalTask):
  """Drop old Invalidate rows when there are too many of them."""

  def HandleRequest(self, mr):
    """Drop excessive rows in the Invalidate table and return some stats.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format.  The stats are just for debugging,
      they are not used by any other part of the system.
    """
    tbl = self.services.cache_manager.invalidate_tbl
    old_count = tbl.SelectValue(mr.cnxn, 'COUNT(*)')

    # Delete anything other than the last 1000 rows because we won't
    # look at them anyway.  If a job gets a request and sees 1000 new
    # rows, it will drop all caches of all types, so it is as if there
    # were 
    if old_count > MAX_INVALIDATE_ROWS_TO_CONSIDER:
      kept_timesteps = tbl.Select(
        mr.cnxn, ['timestep'],
        order_by=[('timestep DESC', [])],
        limit=MAX_INVALIDATE_ROWS_TO_CONSIDER)
      earliest_kept = kept_timesteps[-1][0]
      tbl.Delete(mr.cnxn, where=[('timestep < %s', [earliest_kept])])
    
    new_count = tbl.SelectValue(mr.cnxn, 'COUNT(*)')

    return {
      'old_count': old_count,
      'new_count': new_count,
      }
