# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import monitoring
from model.wf_try_bot_cache import WfTryBot
from model.wf_try_bot_cache import WfTryBotCache
from waterfall.test import wf_testcase


class WfTryBotCacheTest(wf_testcase.WaterfallTestCase):

  def testAddFirstBot(self):
    bot_id = 'fake_slave_123'
    cache = WfTryBotCache.Get('new_cache_empty')
    self.assertFalse(cache.recent_bots)
    cache.AddBot(bot_id, 123, 456)
    self.assertIn(bot_id, cache.recent_bots)

  def testNoDuplicates(self):
    cache = WfTryBotCache.Get('new_cache_no_dupes')
    self.assertFalse(cache.recent_bots)
    bot_id = 'fake_slave_123'
    cache.AddBot(bot_id, 123, 456)
    cache.AddBot(bot_id, 124, 456)
    cache.AddBot(bot_id, 125, 456)
    self.assertEqual(1, len(cache.recent_bots))

  def testMoveToFront(self):
    cache = WfTryBotCache.Get('new_cache_move_to_front')
    cache.recent_bots = ['bot1', 'bot2']
    cache.AddBot('bot2', 123, 456)
    self.assertEqual(['bot2', 'bot1'], cache.recent_bots)

  def testAddFullBuild(self):
    cache_name = 'full_build_new_cache'
    bot_id = 'full_build_bot'
    dimensions = [{
        'key': 'caches',
        'value': [cache_name, 'some_other_cache'],
    }, {
        'key': 'os',
        'value': ['Windows', 'Windows2008R2'],
    }]

    cache = WfTryBotCache.Get(cache_name)
    cache.AddFullBuild(bot_id, 1000, dimensions)
    cache.put()

    # Make sure the bot has both caches in datastore.
    saved_bot = WfTryBot.Get(bot_id)
    self.assertEqual(
        set([cache_name, 'some_other_cache']), set(saved_bot.caches))

    # Make sure cache has bot, and built commit position.
    saved_cache = WfTryBotCache.Get(cache_name)
    self.assertIn(bot_id, saved_cache.full_build_commit_positions)
    self.assertEqual(1000, saved_cache.full_build_commit_positions[bot_id])

  @mock.patch.object(monitoring, 'cache_evictions')
  def testAddFullBuildEvictionDetection(self, mockEvictionMetric):
    cache_name = 'full_build_existing_cache'
    bot_id = 'full_build_bot_2'
    dimensions = [{
        'key': 'caches',
        'value': [cache_name, 'some_other_cache'],
    }, {
        'key': 'os',
        'value': ['Windows', 'Windows2008R2'],
    }]

    cache = WfTryBotCache.Get(cache_name)
    cache.AddFullBuild(bot_id, 1000, dimensions)
    cache.put()
    dimensions = [
        {
            'key': 'caches',
            'value': [cache_name],  # Removed 'some_other_cache'.
        },
        {
            'key': 'os',
            'value': ['Windows', 'Windows2008R2'],
        }
    ]

    cache = WfTryBotCache.Get(cache_name)
    cache.AddFullBuild(bot_id, 1001, dimensions)
    cache.put()

    # Make sure the bot has correct caches in datastore.
    saved_bot = WfTryBot.Get(bot_id)
    self.assertNotIn('some_other_cache', saved_bot.caches)
    self.assertIn(cache_name, saved_bot.caches)

    # Make sure cache has bot, and built commit position.
    saved_cache = WfTryBotCache.Get(cache_name)
    self.assertIn(bot_id, saved_cache.full_build_commit_positions)
    self.assertEqual(1001, saved_cache.full_build_commit_positions[bot_id])

    # Make sure metric incremented.
    self.assertTrue(
        mockEvictionMetric.increment.called_once_with({
            'platform': 'windows'
        }))
