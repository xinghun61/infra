# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
from datetime import datetime
import json
import logging
import mock
import os
import urllib

from libs.http.retry_http_client import RetryHttpClient
from model.wf_config import FinditConfig
from model.wf_try_bot_cache import WfTryBot
from model.wf_try_bot_cache import WfTryBotCache
from services import swarmbot_util
from waterfall import swarming_util
from waterfall.test import wf_testcase


class MockBuild(object):

  def __init__(self, response):
    self.response = response


MOCK_BUILDS = [(None,
                MockBuild({
                    'tags': [
                        'swarming_tag:log_location:logdog://host/project/path'
                    ]
                }))]

ALL_BOTS = [{'bot_id': 'bot%d' % b} for b in range(10)]
SOME_BOTS = [{'bot_id': 'bot%d' % b} for b in range(3)]
ONE_BOT = [{'bot_id': 'bot%d' % b} for b in range(1)]


class MockTryJob(object):

  def __init__(self):
    self.is_swarmbucket_build = True
    self.dimensions = ['os:OS', 'cpu:CPU']
    self.properties = {'bad_revision': 'a1b2c3d4'}


class MockFlakeTryJob(object):

  def __init__(self):
    self.is_swarmbucket_build = True
    self.dimensions = ['os:OS', 'cpu:CPU']
    self.properties = {'test_revision': 'a1b2c3d4'}


class SwarmbotUtilTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(SwarmbotUtilTest, self).setUp()
    self.buildbucket_id = '88123'
    self.step_name = 'browser_tests on platform'

  def testGetCacheName(self):
    cache_name_a = swarmbot_util.GetCacheName('luci.chromium.findit',
                                              'linux_chromium_variable')
    cache_name_b = swarmbot_util.GetCacheName('luci.chromium.findit',
                                              'win_chromium_variable')
    cache_name_c = swarmbot_util.GetCacheName('luci.chromium.ci',
                                              'win_chromium_variable')
    cache_name_d = swarmbot_util.GetCacheName('luci.chromium.ci',
                                              'win_chromium_variable', 'flake')

    self.assertTrue(cache_name_a.startswith('builder_'))
    self.assertTrue(cache_name_b.startswith('builder_'))
    self.assertTrue(cache_name_c.startswith('builder_'))
    self.assertTrue(cache_name_d.startswith('builder_'))
    self.assertTrue(cache_name_d.endswith('_flake'))
    self.assertNotEqual(cache_name_a, cache_name_b)
    self.assertNotEqual(cache_name_a, cache_name_c)
    self.assertNotEqual(cache_name_b, cache_name_c)
    self.assertNotEqual(cache_name_c, cache_name_d)

  def testGetBot(self):

    class MockBuildbucketBuild(object):
      response = {
          'result_details_json':
              json.dumps({
                  'swarming': {
                      'task_result': {
                          'bot_id': 'slave777-c4'
                      }
                  }
              })
      }

    self.assertEqual('slave777-c4', swarmbot_util.GetBot(MockBuildbucketBuild))

  def testGetBotNotFound(self):

    class MockBuildbucketBuild(object):
      response = {'result_details_json': json.dumps({})}

    self.assertIsNone(swarmbot_util.GetBot(MockBuildbucketBuild))
    MockBuildbucketBuild.response = {}
    self.assertIsNone(swarmbot_util.GetBot(MockBuildbucketBuild))

  def testGetBuilderCacheName(self):

    class MockBuildbucketBuild(object):
      response = {
          'parameters_json':
              json.dumps({
                  'swarming': {
                      'override_builder_cfg': {
                          'caches': [{
                              'path': 'builder',
                              'name': 'builder_dummyhash'
                          }]
                      }
                  }
              })
      }

    self.assertEqual('builder_dummyhash',
                     swarmbot_util.GetBuilderCacheName(MockBuildbucketBuild))

  def testGetBuilderCacheNameNotFound(self):

    class MockBuildbucketBuild(object):
      response = {'parameters_json': json.dumps({'swarming': {}})}

    self.assertIsNone(swarmbot_util.GetBuilderCacheName(MockBuildbucketBuild))
    MockBuildbucketBuild.response = {
        'parameters_json':
            json.dumps({
                'swarming': {
                    'override_builder_cfg': {
                        'caches': [{
                            'path': 'other_cache',
                            'name': 'other_cache_name'
                        }]
                    }
                }
            })
    }
    self.assertIsNone(swarmbot_util.GetBuilderCacheName(MockBuildbucketBuild))
    MockBuildbucketBuild.response = {}
    self.assertIsNone(swarmbot_util.GetBuilderCacheName(MockBuildbucketBuild))

  @mock.patch.object(swarming_util, 'SendRequestToServer')
  def testSelectWarmCacheNoOp(self, mock_fn):

    class MockTryJobBuildbot(object):
      is_swarmbucket_build = False

    try_job_buildbot = MockTryJobBuildbot()
    cache_name = 'some_other_cache_name'
    WfTryBotCache.Get(cache_name).recent_bots = ['slave1']
    swarmbot_util.AssignWarmCacheHost(try_job_buildbot, cache_name, None)
    self.assertFalse(mock_fn.called)

  @mock.patch.object(
      swarming_util,
      'SendRequestToServer',
      return_value=(None, {
          'code': 1,
          'message': 'error'
      }))
  def testGetAllBotsWithCacheError(self, _):
    dimensions = {'os': 'OS', 'cpu': 'cpu'}
    self.assertEqual([],
                     swarmbot_util.GetAllBotsWithCache(dimensions, 'cache_name',
                                                       None))

  @mock.patch.object(swarming_util, 'SendRequestToServer')
  def testGetAllBotsWithCache(self, mock_fn):

    dimensions = {'os': 'OS', 'cpu': 'cpu'}

    content_data = {'items': [{'bot_id': 'bot_1'}]}
    mock_fn.return_value = (json.dumps(content_data), None)
    self.assertEqual(content_data['items'],
                     swarmbot_util.GetAllBotsWithCache(dimensions, 'cache_name',
                                                       None))

  def testOnlyAvailable(self):
    all_bots = [{
        'bot_id': 'bot1',
        'task_id': '123abc000'
    }, {
        'bot_id': 'bot2',
        'is_dead': True
    }, {
        'bot_id': 'bot3',
        'quarantined': True
    }, {
        'bot_id': 'bot4',
        'deleted': True
    }, {
        'bot_id': 'bot5'
    }]
    self.assertEqual([{
        'bot_id': 'bot5'
    }], swarmbot_util.OnlyAvailable(all_bots))

  def testHaveCommitPositionInLocalGitCache(self):
    bots = [{'bot_id': 'bot%d' % i} for i in range(10)]
    bot5 = WfTryBot.Get('bot5')
    bot5.newest_synced_revision = 100
    bot5.put()
    self.assertEqual([{
        'bot_id': 'bot5'
    }], swarmbot_util._HaveCommitPositionInLocalGitCache(bots, 1))

  def testSortByDistanceToCommitPosition(self):
    cache_name = 'cache_name'
    cache_stats = WfTryBotCache.Get(cache_name)
    cache_stats.AddBot('bot1', 80, 80)
    cache_stats.AddBot('bot2', 90, 90)
    cache_stats.AddBot('bot3', 110, 110)
    cache_stats.AddBot('bot4', 120, 120)
    cache_stats.put()
    bots = [{'bot_id': 'bot%d' % i} for i in range(1, 5)]
    closest = swarmbot_util._ClosestEarlier(bots, cache_name, 70)
    self.assertFalse(closest)
    closest = swarmbot_util._ClosestLater(bots, cache_name, 70)
    self.assertEqual({'bot_id': 'bot1'}, closest)

    sorted_bots = swarmbot_util._SortByDistanceToCommitPosition(
        bots, cache_name, 100, False)
    self.assertEqual({'bot_id': 'bot2'}, sorted_bots[0])
    sorted_bots = swarmbot_util._SortByDistanceToCommitPosition(
        bots, cache_name, 121, False)
    self.assertEqual({'bot_id': 'bot4'}, sorted_bots[0])

  def testLeastCrowded(self):
    bots = [{
        'bot_id': 'slave1',
        'dimensions': [{
            'key': 'caches',
            'value': ['builder_123456']
        }],
        'state': json.dumps({
            'disks': {
                'c:\\': {
                    'free_mb': 1000
                }
            }
        })
    }, {
        'bot_id':
            'slave2',
        'dimensions': [{
            'key': 'caches',
            'value': ['builder_123456', 'builder_abcdef']
        }],
        'state':
            json.dumps({
                'disks': {
                    'c:\\': {
                        'free_mb': 1000
                    }
                }
            })
    }, {
        'bot_id':
            'slave3',
        'dimensions': [{
            'key': 'caches',
            'value': ['builder_123456', 'builder_abcdef']
        }],
        'state':
            json.dumps({
                'disks': {
                    'c:\\': {
                        'free_mb': 2000
                    }
                }
            })
    }, {
        'bot_id': 'slave4'
    }]
    # The one with fewer caches is preferred.
    self.assertEqual('slave1',
                     swarmbot_util._GetBotWithFewestNamedCaches(bots)['bot_id'])
    # If there is a tie, the one with more free space is preferred.
    self.assertEqual('slave3',
                     swarmbot_util._GetBotWithFewestNamedCaches(
                         bots[1:])['bot_id'])
    self.assertEqual('slave3',
                     swarmbot_util._GetBotWithFewestNamedCaches(
                         bots[2:])['bot_id'])
    # If a bot does not have the caches dimension or the free space data, it is
    # only selected as a last resort.
    self.assertEqual('slave4',
                     swarmbot_util._GetBotWithFewestNamedCaches(
                         bots[3:])['bot_id'])

  @mock.patch('services.swarmbot_util._GetBotWithFewestNamedCaches',
              lambda x: x[0])
  @mock.patch(
      'services.swarmbot_util.GetAllBotsWithCache', return_value=ALL_BOTS)
  @mock.patch('services.swarmbot_util.OnlyAvailable', return_value=SOME_BOTS)
  def testAssignWarmCacheHostFlake(self, *_):
    cache_name = 'cache_name_flake'
    tryjob = MockFlakeTryJob()
    swarmbot_util.AssignWarmCacheHost(tryjob, cache_name, None)
    self.assertIn('id:' + SOME_BOTS[0]['bot_id'], tryjob.dimensions)

  @mock.patch(
      'services.swarmbot_util.GetAllBotsWithCache', return_value=ALL_BOTS)
  @mock.patch('services.swarmbot_util.logging.error')
  def testAssignWarmCacheHostWithNoRevision(self, mock_error, *_):
    cache_name = 'cache_name'
    tryjob = MockTryJob()
    del tryjob.properties['bad_revision']
    swarmbot_util.AssignWarmCacheHost(tryjob, cache_name, None)
    # Make sure that no bot was selected.
    self.assertEqual(2, len(tryjob.dimensions))
    # Make sure that an error was logged.
    self.assertTrue(mock_error.called)

  @mock.patch(
      'services.swarmbot_util.GetAllBotsWithCache', return_value=ALL_BOTS)
  @mock.patch('services.swarmbot_util.OnlyAvailable', return_value=SOME_BOTS)
  @mock.patch(
      'services.swarmbot_util._HaveCommitPositionInLocalGitCache',
      return_value=SOME_BOTS)
  @mock.patch('services.swarmbot_util._ClosestEarlier', return_value=ONE_BOT[0])
  @mock.patch('services.swarmbot_util._ClosestLater', return_value=ONE_BOT[0])
  @mock.patch('services.swarmbot_util.CachedGitilesRepository.GetChangeLog')
  def testAssignWarmCacheHost(self, *_):
    cache_name = 'cache_name'
    tryjob = MockTryJob()
    swarmbot_util.AssignWarmCacheHost(tryjob, cache_name, None)

    # No bots with cache, check no bot id
    # No bots with rev, check bot_id of only bot with cache
    # No bots with earlier rev, check bot_id with earliest later rev
    # Bot with earlier rev gets assigned.

  @mock.patch(
      'services.swarmbot_util.GetAllBotsWithCache', return_value=ALL_BOTS)
  @mock.patch('services.swarmbot_util.OnlyAvailable', return_value=SOME_BOTS)
  @mock.patch(
      'services.swarmbot_util._HaveCommitPositionInLocalGitCache',
      return_value=SOME_BOTS)
  @mock.patch('services.swarmbot_util._ClosestEarlier', return_value=ONE_BOT[0])
  @mock.patch('services.swarmbot_util.CachedGitilesRepository.GetChangeLog')
  def testAssignWarmCacheHostEarlier(self, *_):
    cache_name = 'cache_name'
    tryjob = MockTryJob()
    swarmbot_util.AssignWarmCacheHost(tryjob, cache_name, None)
    self.assertEqual('id:bot0', tryjob.dimensions[2])

  @mock.patch(
      'services.swarmbot_util.GetAllBotsWithCache', return_value=ALL_BOTS)
  @mock.patch('services.swarmbot_util.OnlyAvailable', return_value=SOME_BOTS)
  @mock.patch(
      'services.swarmbot_util._HaveCommitPositionInLocalGitCache',
      return_value=SOME_BOTS)
  @mock.patch('services.swarmbot_util._ClosestEarlier', return_value=None)
  @mock.patch('services.swarmbot_util._ClosestLater', return_value=ONE_BOT[0])
  @mock.patch('services.swarmbot_util.CachedGitilesRepository.GetChangeLog')
  def testAssignWarmCacheHostLater(self, *_):
    cache_name = 'cache_name'
    tryjob = MockTryJob()
    swarmbot_util.AssignWarmCacheHost(tryjob, cache_name, None)
    self.assertEqual('id:bot0', tryjob.dimensions[2])

  @mock.patch('services.swarmbot_util._GetBotWithFewestNamedCaches',
              lambda x: x[0])
  @mock.patch(
      'services.swarmbot_util.GetAllBotsWithCache', return_value=ALL_BOTS)
  @mock.patch('services.swarmbot_util.OnlyAvailable', return_value=SOME_BOTS)
  @mock.patch(
      'services.swarmbot_util._HaveCommitPositionInLocalGitCache',
      return_value=ONE_BOT)
  @mock.patch('services.swarmbot_util._ClosestEarlier', return_value=None)
  @mock.patch('services.swarmbot_util._ClosestLater', return_value=None)
  @mock.patch('services.swarmbot_util.CachedGitilesRepository.GetChangeLog')
  def testAssignWarmCacheHostNoCheckedOutRevision(self, *_):
    cache_name = 'cache_name'
    tryjob = MockTryJob()
    swarmbot_util.AssignWarmCacheHost(tryjob, cache_name, None)
    self.assertEqual('id:bot0', tryjob.dimensions[2])

  @mock.patch('services.swarmbot_util._GetBotWithFewestNamedCaches',
              lambda x: x[0])
  @mock.patch(
      'services.swarmbot_util.GetAllBotsWithCache', return_value=ALL_BOTS)
  @mock.patch('services.swarmbot_util.OnlyAvailable', return_value=ONE_BOT)
  @mock.patch(
      'services.swarmbot_util._HaveCommitPositionInLocalGitCache',
      return_value=[])
  @mock.patch('services.swarmbot_util.CachedGitilesRepository.GetChangeLog')
  def testAssignWarmCacheHostNoCachedRevision(self, *_):
    cache_name = 'cache_name'
    tryjob = MockTryJob()
    swarmbot_util.AssignWarmCacheHost(tryjob, cache_name, None)
    self.assertEqual('id:bot0', tryjob.dimensions[2])

  @mock.patch('services.swarmbot_util.GetBotsByDimension', return_value=[])
  @mock.patch('services.swarmbot_util.GetAllBotsWithCache', return_value=[])
  @mock.patch('services.swarmbot_util.OnlyAvailable', return_value=[])
  @mock.patch('services.swarmbot_util.CachedGitilesRepository.GetChangeLog')
  def testAssignWarmCacheNoIdleBots(self, *_):
    cache_name = 'cache_name'
    tryjob = MockTryJob()
    swarmbot_util.AssignWarmCacheHost(tryjob, cache_name, None)
    self.assertEqual(2, len(tryjob.dimensions))

  @mock.patch('services.swarmbot_util.GetAllBotsWithCache', return_value=[])
  @mock.patch(
      'services.swarmbot_util.GetBotsByDimension', return_value=ALL_BOTS)
  @mock.patch('services.swarmbot_util.OnlyAvailable', lambda x: x)
  @mock.patch('services.swarmbot_util.CachedGitilesRepository.GetChangeLog')
  @mock.patch('services.swarmbot_util._GetBotWithFewestNamedCaches',
              lambda x: x[0])
  def testAssignWarmCacheOnlyIdleBots(self, *_):
    cache_name = 'cache_name'
    tryjob = MockTryJob()
    swarmbot_util.AssignWarmCacheHost(tryjob, cache_name, None)
    self.assertEqual('id:bot0', tryjob.dimensions[2])

  @mock.patch.object(
      swarming_util, 'SendRequestToServer', return_value=(None, None))
  def testGetBotsByDimensionNoContent(self, _):
    self.assertEqual([], swarmbot_util.GetBotsByDimension([], None))
