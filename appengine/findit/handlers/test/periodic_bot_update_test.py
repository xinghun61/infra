# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock

import webapp2

from common.waterfall import buildbucket_client
from common.waterfall import pubsub_callback
from gae_libs import token
from handlers import periodic_bot_update
from waterfall import swarming_util
from waterfall.test import wf_testcase


class PeriodicBotUpdateTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/periodic-bot-update', periodic_bot_update.PeriodicBotUpdate),
      ],
      debug=True)

  @mock.patch.object(periodic_bot_update, '_TriggerUpdateJobs')
  def testHandleGet(self, mock_fn):
    mock_fn.return_value = [(None, buildbucket_client.BuildbucketBuild({
        'id': '1',
        'url': 'url',
        'status': 'SCHEDULED',
    })), (buildbucket_client.BuildbucketError({
        'reason': 'Fake reason',
        'message': 'Fake message'
    }), None)]
    response = self.test_app.get(
        '/periodic-bot-update',
        headers={'X-AppEngine-Cron': 'true'},
    )
    self.assertEqual(200, response.status_int)
    self.assertIsInstance(response.json_body, dict)
    self.assertIn('builds', response.json_body)
    self.assertIn('errors', response.json_body)

  @mock.patch.object(
      pubsub_callback,
      'GetTryJobTopic',
      return_value='projects/findit-for-me/topics/jobs')
  @mock.patch.object(token, 'GenerateAuthToken', return_value='auth_token')
  def testBotUpdateTryJob(self, *_):
    request_linux = periodic_bot_update._BotUpdateTryJob('bot1', 'Linux')
    self.assertEqual({
        'parameters_json':
            json.dumps({
                'swarming': {
                    'override_builder_cfg': {
                        'recipe': {
                            'name': 'findit/chromium/preemptive_bot_update'
                        },
                        'dimensions': ['id:bot1', 'pool:Chrome.Findit'],
                        'caches': [{
                            'path': 'builder',
                            'name': 'builder_908bcf0b6984d585a05cf6c94016'
                                    'f0425fbd74af0593a36f8574ab6a2762e7a1'
                        }]
                    }
                },
                'builder_name': 'LUCI linux_chromium_variable',
                'properties': {
                    'recipe': 'findit/chromium/preemptive_bot_update'
                }
            }),
        'bucket':
            'luci.chromium.try',
        'pubsub_callback': {
            'topic':
                'projects/findit-for-me/topics/jobs',
            'auth_token':
                'auth_token',
            'user_data':
                json.dumps({
                    'Message-Type': 'BuildbucketStatusChange',
                    'Notification-Id': ''
                })
        },
        'tags': ['user_agent:findit']
    }, request_linux.ToBuildbucketRequest())

    request_win = periodic_bot_update._BotUpdateTryJob('bot2', 'Windows')
    win_params = json.loads(
        request_win.ToBuildbucketRequest()['parameters_json'])
    self.assertIn('win_chromium_variable', win_params['builder_name'])

    request_mac = periodic_bot_update._BotUpdateTryJob('bot3', 'Mac')
    mac_params = json.loads(
        request_mac.ToBuildbucketRequest()['parameters_json'])
    self.assertIn('mac_chromium_variable', mac_params['builder_name'])

  @mock.patch.object(swarming_util, 'GetBotsByDimension')
  def testTriggerUpdateJobsNoBots(self, mock_get_bots):
    mock_get_bots.return_value = []
    self.assertEqual([], periodic_bot_update._TriggerUpdateJobs())

  @mock.patch.object(swarming_util, 'GetBotsByDimension')
  @mock.patch.object(buildbucket_client, 'TriggerTryJobs')
  def testTriggerUpdateJobs(self, mock_trigger, mock_get_bots):
    mock_get_bots.return_value = [{
        'bot_id': 'bot_1'
    }, {
        'bot_id': 'bot_2',
        'task_id': '1'
    }]
    periodic_bot_update._TriggerUpdateJobs()
    # Only one call to TriggerTryJobs.
    self.assertEqual(1, len(mock_trigger.call_args_list))
    # But with three separate builds (one per OS).
    self.assertEqual(3, len(mock_trigger.call_args_list[0][0][0]))
