# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class WfTryBot(ndb.Model):
  """Represents a single bot in the pool.

  Useful to keep state about the bot shared accross different builders that use
  it. Such as the local git cache.
  """
  newest_synced_revision = ndb.IntegerProperty(indexed=False)

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
  # There is no point in keeping too long a list of bots.
  MAX_RECENT_BOTS = 10
  MAX_CACHE_TIMES = 1000

  # This contains a list of bot_id strings, for the bots that recently completed
  # a build using this cache name successfully. The order of the list indicates
  # which slaves last completed a job with the named cache, with the most recent
  # one at the lowest index.
  recent_bots = ndb.StringProperty(indexed=False, repeated=True)

  # These lists of ints should track how long it takes to complete a task on
  # both cache states so that we can compute the expected time savings of using
  # a warm cache and make better decisions when resources are constrained.
  # These are to be truncated at MAX_CACHE_TIMES entries.
  cold_cache_times = ndb.JsonProperty(indexed=False, compressed=True)
  warm_cache_times = ndb.JsonProperty(indexed=False, compressed=True)

  # This dict maps a bot_id to the last revision it synced to.
  checked_out_commit_positions = ndb.JsonProperty(
      indexed=False, compressed=False)

  @staticmethod
  def Get(cache_name):
    key = ndb.Key('WfTryBotCache', cache_name)
    result = key.get()
    if not result:
      result = WfTryBotCache(
          key=key,
          recent_bots=[],
          cold_cache_times=[],
          warm_cache_times=[],
          checked_out_commit_positions={})
      result.put()
    return result

  def AddBot(self, bot_id, checked_out_cp, cached_cp):
    """Records a bot's used cache and cached/checked out revisions."""

    # Initialize if necessary.
    self.recent_bots = self.recent_bots or []
    self.checked_out_commit_positions = self.checked_out_commit_positions or {}

    self.checked_out_commit_positions[bot_id] = checked_out_cp
    bot = WfTryBot.Get(bot_id)
    bot.newest_synced_revision = cached_cp
    bot.put()

    # If the bot is already at the front of the list do nothing.
    if self.recent_bots and self.recent_bots[0] == bot_id:
      return

    if bot_id in self.recent_bots:
      self.recent_bots.remove(bot_id)

    self.recent_bots.insert(0, bot_id)

    # Truncate to size.
    if len(self.recent_bots) > self.MAX_RECENT_BOTS:
      self.recent_bots = self.recent_bots[:self.MAX_RECENT_BOTS]
      # Truncate checked_out_commit_positions as well.
      # Use .keys() explicitly rather than iterating over the dictionary because
      # the clause may remove elements.
      for bot_id in self.checked_out_commit_positions.keys():
        if bot_id not in self.recent_bots:
          del (self.checked_out_commit_positions[bot_id])

  def AddCacheTime(self, t, cold=False):
    times = self.cold_cache_times if cold else self.warm_cache_times
    times.append(t)
    if len(times) > self.MAX_CACHE_TIMES:
      # Keep only the last MAX_CACHE_TIMES values.
      if cold:
        self.cold_cache_times = times[-self.MAX_CACHE_TIMES:]
      else:
        self.warm_cache_times = times[-self.MAX_CACHE_TIMES:]
