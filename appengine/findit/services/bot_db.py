# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions to get bot configurations from chromium's waterfalls.

This module relies on a periodic batch process that exports the configuration
for the bots from the chromium_tests recipe module onto a google storage file.
"""
import json

import cloudstorage as gcs

from gae_libs.caches import CompressedMemCache
from libs.cache_decorator import Cached

_BOT_DB_PATH = '/findit-for-me/bot_db.json'


class BotDBException(Exception):
  pass


@Cached(
    # We use compressed memcache because the bot_db could become larger than
    # 1MB.
    CompressedMemCache(),
    namespace='bot_db',
    # The bot_db is dumped every 6 hours, caching for 1 hour makes the worst
    # case latency about 7 hours. This still achives detecting new bots in less
    # than a day without excessive polling.
    expire_time=3600)
def _GetBotDB():
  try:
    bot_db_text = gcs.open(_BOT_DB_PATH).read()
    # Casting as dict because the bot_db is exported as a list of k, v pairs.
    bot_db = dict(json.loads(bot_db_text))
  except (ValueError, gcs.Error) as e:
    raise BotDBException('Bot DB export is invalid or unavailable in %s: %s ' %
                         (_BOT_DB_PATH, e.message))
  return bot_db


def GetBuilders(master_filter=None, bot_type_filter=None, platform_filter=None):
  """Gets all builders in the db that match the given parameters.

  If any of the parameters is None, do not filter based on it.

  Args:
    - master_filter (list of str): Which masters to get builders for.
    - bot_type_filter (list of str): Which types of builders to include
        e.g.  'tester', 'builder'.
    - platform_filter (list of str): Which platforms to include. e.g.
        'win',' 'linux'

  Returns:
    List of tuples: (mastername, buildername).
  """
  result = []
  for master_name, master_db in _GetBotDB().iteritems():
    if master_filter and master_name not in master_filter:
      continue
    for builder_name, builder_config in master_db.get('builders',
                                                      {}).iteritems():
      if bot_type_filter and builder_config.get('bot_type',
                                                'None') not in bot_type_filter:
        continue
      if platform_filter and builder_config.get('testing', {}).get(
          'platform', 'None') not in platform_filter:
        continue
      result.append((master_name, builder_name))

  return result
