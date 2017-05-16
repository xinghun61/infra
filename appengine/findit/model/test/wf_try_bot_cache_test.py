# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.wf_try_bot_cache import WfTryBotCache
from waterfall.test import wf_testcase


class WfTryBotCacheTest(wf_testcase.WaterfallTestCase):

  def testAddFirstBot(self):
    bot_id = 'fake_slave_123'
    cache = WfTryBotCache.Get('new_cache_empty')
    self.assertFalse(cache.recent_bots)
    cache.AddBot(bot_id)
    self.assertIn(bot_id, cache.recent_bots)

  def testNoDuplicates(self):
    cache = WfTryBotCache.Get('new_cache_no_dupes')
    self.assertFalse(cache.recent_bots)
    bot_id = 'fake_slave_123'
    cache.AddBot(bot_id)
    cache.AddBot(bot_id)
    cache.AddBot(bot_id)
    self.assertEqual(1, len(cache.recent_bots))

  def testMoveToFront(self):
    cache = WfTryBotCache.Get('new_cache_move_to_front')
    cache.recent_bots = ['bot1', 'bot2']
    cache.AddBot('bot2')
    self.assertEqual(['bot2', 'bot1'], cache.recent_bots)

  def testTruncateList(self):
    init_cache = WfTryBotCache.Get('popular_cache')
    init_cache.recent_bots = ['bot%d' % x for x in
                         range(WfTryBotCache.MAX_RECENT_BOTS)]
    init_cache.put()
    cache = WfTryBotCache.Get('popular_cache')
    self.assertEqual(WfTryBotCache.MAX_RECENT_BOTS, len(cache.recent_bots))
    cache.AddBot('fake_slave_123')
    self.assertEqual(WfTryBotCache.MAX_RECENT_BOTS, len(cache.recent_bots))
    self.assertEqual('fake_slave_123', cache.recent_bots[0])

  def testAddCacheTime(self):
    cache = WfTryBotCache.Get('new_cache_add_time')
    for _ in range(cache.MAX_CACHE_TIMES + 10):
      cache.AddCacheTime(1, True)
      cache.AddCacheTime(1, False)
    self.assertEqual(cache.MAX_CACHE_TIMES, len(cache.cold_cache_times))
    self.assertEqual(cache.MAX_CACHE_TIMES, len(cache.warm_cache_times))
