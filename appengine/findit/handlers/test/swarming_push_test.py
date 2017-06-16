# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json

import mock
import webapp2

from testing_utils import testing

from common.waterfall import pubsub_callback
from gae_libs import token
from handlers.swarming_push import SwarmingPush
from model.wf_swarming_task import WfSwarmingTask


class SwarmingPushTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/pubsub/swarmingpush', SwarmingPush),], debug=True)

  def setUp(self):
    super(SwarmingPushTest, self).setUp()

  # Send well formed notification for job that does not exist
  @mock.patch.object(token, 'ValidateAuthToken', return_value=True)
  @mock.patch('logging.warning')
  def testSwarmingPushMissingTask(self, logging_mock, _):
    self.test_app.post('/pubsub/swarmingpush', params={
        'data': json.dumps({
            'message':{
                'attributes':{
                    'auth_token': 'auth_token',
                },
                'data': base64.b64encode(json.dumps({
                    'task_id': '12345',
                    'userdata': json.dumps({
                        'Message-Type': 'SwarmingTaskStatusChange',
                    }),
                })),
            },
        }),
        'format': 'json',
    })
    self.assertTrue(logging_mock.called)


  # ill formed notification (bad token)
  @mock.patch.object(token, 'ValidateAuthToken', return_value=False)
  def testSwarmingPushBadToken(self, _):
    # We expect a 400 error, and a webtest.webtest.AppError (not in path,
    # catching plain Exception)
    with self.assertRaisesRegexp(Exception, '.*400.*'):
      _ = self.test_app.post('/pubsub/swarmingpush', params={
          'data': json.dumps({
              'message':{
                  'attributes':{
                      'auth_token': 'BadTokenString',
                  },
                  'data': base64.b64encode(json.dumps({
                      'task_id': '12345',
                      'userdata': json.dumps({
                          'Message-Type': 'SwarmingTaskStatusChange',
                      }),
                  })),
              },
          }),
        'format': 'json',
      })

  # Send notification with unsupported message-type
  @mock.patch.object(token, 'ValidateAuthToken', return_value=True)
  def testSwarmingPushUnsupportedMessageType(self, _):
    # We expect a 500 error, and a webtest.webtest.AppError (not in path,
    # catching plain Exception)
    with self.assertRaisesRegexp(Exception, '.*500.*'):
      _ = self.test_app.post('/pubsub/swarmingpush', params={
          'data': json.dumps({
              'message':{
                  'attributes':{
                      'auth_token': 'auth_token',
                  },
                  'data': base64.b64encode(json.dumps({
                      'task_id': '8988270260466361040',
                      'userdata': json.dumps({
                          # Should break beacause of this
                          'Message-Type': 'HyperLoopSpaceJump',
                      }),
                  })),
              },
          }),
        'format': 'json',
      })

  # Send well formed notification
  @mock.patch.object(token, 'ValidateAuthToken', return_value=True)
  def testSwarmingPush(self, _):
    task = WfSwarmingTask.Create('m', 'b', 1, 'test')
    task.task_id = '12345'
    task.callback_url = '/callback?pipeline_id=f9f89162ef32c7fb7'
    task.put()

    with mock.patch('google.appengine.api.taskqueue.add') as mock_queue:
      self.test_app.post('/pubsub/swarmingpush', params={
          'data': json.dumps({
              'message':{
                  'attributes':{
                      'auth_token': 'auth_token',
                  },
                  'data': base64.b64encode(json.dumps({
                      'task_id': '12345',
                      'userdata': json.dumps({
                          'Message-Type': 'SwarmingTaskStatusChange',
                      }),
                  })),
              },
          }),
          'format': 'json',
      })
      mock_queue.assert_called_once()

  @mock.patch.object(token, 'ValidateAuthToken', return_value=True)
  @mock.patch('logging.warning')
  def testSwarmingPushMissingCallback(self, logging_mock, _):
    task = WfSwarmingTask.Create('m', 'b', 1, 'test')
    task.task_id = '12345'
    task.put()

    # This should not break, so that pubsub does not keep retrying. We'll only
    # log a message.
    self.test_app.post('/pubsub/swarmingpush', params={
        'data': json.dumps({
            'message':{
                'attributes':{
                    'auth_token': 'auth_token',
                },
                'data': base64.b64encode(json.dumps({
                    'task_id': '12345',
                    'userdata': json.dumps({
                        'Message-Type': 'SwarmingTaskStatusChange',
                    }),
                })),
            },
        }),
        'format': 'json',
    })
    self.assertTrue(logging_mock.called)
