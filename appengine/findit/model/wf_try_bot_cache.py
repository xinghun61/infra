# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb
from common import monitoring


class WfTryBot(ndb.Model):
  """Represents a single bot in the pool.

  Useful to keep state about the bot shared accross different builders that use
  it. Such as the local git cache.
  """
  newest_synced_revision = ndb.IntegerProperty(indexed=False)

  caches = ndb.StringProperty(indexed=False, repeated=True)

  def SetCaches(self, dimensions):
    """Updates the list of available caches, removes records of evicted caches.

    Args:
      dimensions: List of dicts as returned by the swarming api in the form
          [{'key': 'id', 'value':['bot_id']}, ...]
    """
    updated_caches = []
    os_values = []
    for d in dimensions:
      if updated_caches and os_values:
        break
      if d.get('key') == 'caches':
        updated_caches = d.get('value')
        continue
      if d.get('key') == 'os':
        os_values = d.get('value')
        continue

    new_caches = set(updated_caches) - set(self.caches)
    for cache in new_caches:
      self.caches.append(cache)

    evicted_caches = set(self.caches) - set(updated_caches)
    for cache in evicted_caches:
      self.caches.remove(cache)
      # Use the shortest variant of the os name as the platform.
      # e.g. (Linux|Mac|Windows) without version.
      platform = min(os_values, key=len)
      monitoring.cache_evictions.increment({'platform': platform})

  @staticmethod
  def Get(bot_id):
    key = ndb.Key('WfTryBot', bot_id)
    result = key.get()
    if not result:
      result = WfTryBot(key=key, newest_synced_revision=None)
      result.put()
    return result


class WfTryBotCache(ndb.Model):
  """Represents a named cache on swarming-backed trybots.

  The purpose is to track which bots have a warm cache, and to accumulate
  statistics about what the time advantage is for using a specific warm cache.
  """

  # This contains a list of bot_id strings, for the bots that recently completed
  # a build using this cache name successfully. The order of the list indicates
  # which slaves last completed a job with the named cache, with the most recent
  # one at the lowest index.
  recent_bots = ndb.StringProperty(indexed=False, repeated=True)

  # This dict maps a bot_id to the last revision it synced to.
  checked_out_commit_positions = ndb.JsonProperty(
      indexed=False, compressed=False)

  # This dict maps a bot_id to the last revision that was fully built.
  full_build_commit_positions = ndb.JsonProperty(
      indexed=False, compressed=False)

  @staticmethod
  def Get(cache_name):
    key = ndb.Key('WfTryBotCache', cache_name)
    result = key.get()
    if not result:
      result = WfTryBotCache(
          key=key,
          recent_bots=[],
          full_build_commit_positions={},
          checked_out_commit_positions={})
      result.put()
    if result.full_build_commit_positions is None:
      # Back-fill this newly added property with the default empty value.
      result.full_build_commit_positions = {}
      result.put()
    return result

  def AddBot(self, bot_id, checked_out_cp, cached_cp, dimensions=None):
    """Records a bot's used cache and cached/checked out revisions."""

    # Initialize if necessary.
    self.recent_bots = self.recent_bots or []
    self.checked_out_commit_positions = self.checked_out_commit_positions or {}

    self.checked_out_commit_positions[bot_id] = checked_out_cp
    bot = WfTryBot.Get(bot_id)
    bot.newest_synced_revision = cached_cp
    if dimensions:
      bot.SetCaches(dimensions)
    bot.put()

    # If the bot is already at the front of the list do nothing.
    if self.recent_bots and self.recent_bots[0] == bot_id:
      return

    if bot_id in self.recent_bots:
      self.recent_bots.remove(bot_id)

    self.recent_bots.insert(0, bot_id)

  def AddFullBuild(self, bot_id, build_cp, dimensions):
    """Records that a full build completed for this cache name on this bot.

    Args:
      bot_id (str): The bot id of the bot where the build took place.
      build_cp (int): The commit position of the revision that was checked out
          and built.
      dimensions (list of str): Dimensions of the bot as returned by swarming
          api.
    """
    self.full_build_commit_positions = self.full_build_commit_positions or {}
    self.full_build_commit_positions[bot_id] = build_cp
    self.AddBot(bot_id, build_cp, build_cp, dimensions)
