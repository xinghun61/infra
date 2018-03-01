# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.findit_http_client import FinditHttpClient
from common.waterfall import buildbucket_client
from model.build_ahead_try_job import BuildAheadTryJob
from services import build_ahead
from services import git
from services import swarmbot_util
from waterfall.test import wf_testcase

CN = 'builder_cc0b584fcab5ab502af9c154891c705115ea1fefd4d176cabf5d04ae0cd4e18c'


class BuildAheadTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(buildbucket_client, 'TriggerTryJobs')
  def testBuildAhead(self, mock_trigger):
    _ = build_ahead.TriggerBuildAhead('master2', 'builder5', 'some_bot')
    mock_trigger.assert_called_once_with([
        buildbucket_client.TryJob(
            master_name='luci.chromium.findit',
            builder_name='findit_variable',
            properties={
                'recipe': 'findit/chromium/compile',
                'good_revision': 'HEAD~1',
                'target_mastername': 'master2',
                'mastername': 'tryserver2',
                'suspected_revisions': [],
                'target_buildername': 'builder5',
                'bad_revision': 'HEAD'
            },
            tags=[],
            additional_build_parameters=None,
            cache_name=CN,
            dimensions=[
                'os:Mac-10.9', 'cpu:x86-64', 'pool:luci.chromium.findit',
                'id:some_bot'
            ],
            pubsub_callback=None)
    ])

  @mock.patch.object(FinditHttpClient, 'Get')
  def testTreeIsOpen(self, mock_get):
    responses = [
        (500, None),
        (400, None),
        (200, None),
        (200, '[]'),
        (200, '[{}]'),
        (200, '[{"general_state":"closed"}]'),
        (200, '[{"general_state":"open"}]'),
    ]
    mock_get.side_effect = responses

    for _ in range(len(responses) - 1):
      self.assertFalse(build_ahead.TreeIsOpen())

    self.assertTrue(build_ahead.TreeIsOpen())

  @mock.patch.object(buildbucket_client, 'GetTryJobs')
  def testUpdateRunningJobs(self, mock_get_tryjobs):
    build_ahead.UpdateRunningBuilds()
    mock_get_tryjobs.assert_not_called()
    BuildAheadTryJob.Create('80000001', 'unix', 'cache_1').put()
    BuildAheadTryJob.Create('80000002', 'win', 'cache_2').put()
    BuildAheadTryJob.Create('80000003', 'mac', 'cache_3').put()
    mock_get_tryjobs.return_value = [
        (None,
         buildbucket_client.BuildbucketBuild({
             'id': '80000001',
             'status': 'STARTED'
         })),
        (None,
         buildbucket_client.BuildbucketBuild({
             'id': '80000002',
             'status': 'STARTED'
         })),
        (None,
         buildbucket_client.BuildbucketBuild({
             'id': '80000003',
             'status': 'STARTED'
         })),
    ]
    self.assertEqual(3, len(build_ahead.UpdateRunningBuilds()))

    mock_get_tryjobs.return_value = [
        (None,
         buildbucket_client.BuildbucketBuild({
             'id': '80000001',
             'status': 'COMPLETED'
         })),
        (None,
         buildbucket_client.BuildbucketBuild({
             'id': '80000002',
             'status': 'STARTED'
         })),
        (None,
         buildbucket_client.BuildbucketBuild({
             'id': '80000003',
             'status': 'STARTED'
         })),
    ]
    self.assertEqual(2, len(build_ahead.UpdateRunningBuilds()))

    mock_get_tryjobs.return_value = [
        (None,
         buildbucket_client.BuildbucketBuild({
             'id': '80000002',
             'status': 'COMPLETED'
         })),
        (None,
         buildbucket_client.BuildbucketBuild({
             'id': '80000003',
             'status': 'COMPLETED'
         })),
    ]
    self.assertEqual(0, len(build_ahead.UpdateRunningBuilds()))

    BuildAheadTryJob.Create('80000004', 'mac', 'cache_4').put()
    mock_get_tryjobs.return_value = [(buildbucket_client.BuildbucketError({
        'reason': 'BUILD_NOT_FOUND',
        'message': 'BUILD_NOT_FOUND'
    }), None)]

    self.assertEqual(0, len(build_ahead.UpdateRunningBuilds()))
    self.assertTrue(BuildAheadTryJob.Get('80000004').running)

  @mock.patch.object(git, 'CountRecentCommits')
  def testLowRepoActivity(self, mock_count_commits):
    mock_count_commits.side_effect = [i for i in range(10)]
    for i in range(4):
      self.assertTrue(build_ahead._LowRepoActivity())
    for i in range(6):
      self.assertFalse(build_ahead._LowRepoActivity())

  def testPlatformToDimensions(self):
    self.assertEqual(['os:Mac'], build_ahead._PlatformToDimensions('mac'))
    self.assertEqual(['os:Windows'], build_ahead._PlatformToDimensions('win'))
    self.assertEqual(['os:Linux'], build_ahead._PlatformToDimensions('unix'))
    self.assertEqual(['os:Linux'], build_ahead._PlatformToDimensions('android'))

  @mock.patch.object(swarmbot_util, 'OnlyAvailable')
  @mock.patch.object(swarmbot_util, 'GetBotsByDimension')
  def testAvailableBotsByPlatform(self, mock_get_bots, mock_available):
    _ = build_ahead._AvailableBotsByPlatform('mac')
    self.assertIn('pool:luci.chromium.findit', mock_get_bots.call_args[0][0])
    self.assertIn('os:Mac', mock_get_bots.call_args[0][0])
    mock_available.assert_called_once()

  @mock.patch.object(build_ahead, '_AvailableBotsByPlatform')
  @mock.patch.object(BuildAheadTryJob, 'RunningJobs')
  @mock.patch.object(build_ahead, '_LowRepoActivity')
  def testPlatformsToBuildHighActivity(self, mock_lo_activity, mock_jobs,
                                       mock_bots):
    mock_lo_activity.return_value = False
    mock_jobs.return_value = []
    self.assertEqual(4, len(build_ahead._PlatformsToBuild()))

    mock_jobs.side_effect = lambda platform: [
        BuildAheadTryJob.Create('1234', platform, 'cache_x')]
    self.assertEqual(0, len(build_ahead._PlatformsToBuild()))

    mock_jobs.side_effect = [
        [BuildAheadTryJob.Create('1234', 'android', 'cache_x')],
        [],
        [],
        [],
    ]
    self.assertEqual(3, len(build_ahead._PlatformsToBuild()))

    mock_jobs.side_effect = [
        [],
        [BuildAheadTryJob.Create('1235', 'mac', 'cache_y')],
        [BuildAheadTryJob.Create('1236', 'unix', 'cache_z')],
        [BuildAheadTryJob.Create('1237', 'win', 'cache_a')],
    ]
    self.assertEqual(1, len(build_ahead._PlatformsToBuild()))
    mock_bots.assert_not_called()

  @mock.patch.object(build_ahead, '_AvailableBotsByPlatform')
  @mock.patch.object(BuildAheadTryJob, 'RunningJobs')
  @mock.patch.object(build_ahead, '_LowRepoActivity')
  def testPlatformsToBuildLowActivity(self, mock_lo_activity, mock_jobs,
                                      mock_bots):
    mock_lo_activity.return_value = True
    mock_jobs.side_effect = [
        [],
        [BuildAheadTryJob.Create('1235', 'mac', 'cache_y')],
        [BuildAheadTryJob.Create('1236', 'unix', 'cache_z')],
        [BuildAheadTryJob.Create('1237', 'win', 'cache_a')],
    ]
    mock_bots.side_effect = [
        [{
            'id': 'bot1'
        }],
        [],
        [{
            'id': 'bot2'
        }],
        [{
            'id': 'bot3'
        }, {
            'id': 'bot4'
        }],
    ]
    self.assertEqual(['android', 'win'], build_ahead._PlatformsToBuild())
