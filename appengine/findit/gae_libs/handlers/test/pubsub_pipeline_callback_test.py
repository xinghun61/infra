# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import mock

import webapp2
import webtest

from testing_utils import testing

from gae_libs import token
from gae_libs.handlers.pubsub_pipeline_callback import PubSubPipelineCallback
from gae_libs.pipelines import AsynchronousPipeline


class _PubSubPipelineCallbackImpl(PubSubPipelineCallback):

  auth_scope = 'auth_scope'
  user_id = 'user'

  def GetValidHoursOfAuthToken(self):
    return 10

  def GetAdditionalParameters(self, pubsub_message, payload_message):
    return {
        'param': payload_message['param'],
        'id': pubsub_message['message_id'],
    }


class _DummyAsynchronousPipeline(AsynchronousPipeline):
  input_type = int
  output_type = int


class PubSubPipelineCallbackTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/push', _PubSubPipelineCallbackImpl),
      ], debug=True)

  @mock.patch.object(_DummyAsynchronousPipeline, 'ScheduleCallbackTask')
  @mock.patch.object(
      AsynchronousPipeline,
      'from_id',
      return_value=_DummyAsynchronousPipeline(1))
  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testSucessfulPush(self, mocked_ValidateAuthToken, mocked_from_id,
                        mocked_ScheduleCallbackTask, *_):
    request_body = json.dumps({
        'message': {
            'message_id':
                'unique-message-id',
            'attributes': {
                'auth_token': 'secret',
            },
            'data':
                base64.b64encode(
                    json.dumps({
                        'user_data':
                            json.dumps({
                                'runner_id': 'pipeline-123',
                            }),
                        'param':
                            123,
                    })),
        }
    })
    response = self.test_app.post('/push?format=json', params=request_body)
    self.assertEqual(200, response.status_code)
    mocked_ValidateAuthToken.assert_called_once_with(
        'auth_scope',
        'secret',
        'user',
        action_id='pipeline-123',
        valid_hours=10)
    mocked_from_id.assert_called_once_with('pipeline-123')
    mocked_ScheduleCallbackTask.assert_called_once_with(
        name='unique-message-id',
        parameters={'param': 123,
                    'id': 'unique-message-id'})

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(False, False))
  def testFailedPushDueToInvalidToken(self, *_):
    request_body = json.dumps({
        'message': {
            'message_id':
                'unique-message-id',
            'attributes': {
                'auth_token': 'secret',
            },
            'data':
                base64.b64encode(
                    json.dumps({
                        'user_data':
                            json.dumps({
                                'runner_id': 'pipeline-123',
                            }),
                        'param':
                            123,
                    })),
        }
    })
    response = self.test_app.post('/push?format=json', params=request_body)
    self.assertEqual(200, response.status_code)

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, True))
  def testFailedPushDueToExpiredToken(self, *_):
    request_body = json.dumps({
        'message': {
            'message_id':
                'unique-message-id',
            'attributes': {
                'auth_token': 'secret',
            },
            'data':
                base64.b64encode(
                    json.dumps({
                        'user_data':
                            json.dumps({
                                'runner_id': 'pipeline-123',
                            }),
                        'param':
                            123,
                    })),
        }
    })
    response = self.test_app.post('/push?format=json', params=request_body)
    self.assertEqual(200, response.status_code)

  @mock.patch.object(AsynchronousPipeline, 'from_id', return_value=None)
  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testFailedPushDueToPipelineNotFound(self, *_):
    request_body = json.dumps({
        'message': {
            'message_id':
                'unique-message-id',
            'attributes': {
                'auth_token': 'secret',
            },
            'data':
                base64.b64encode(
                    json.dumps({
                        'user_data':
                            json.dumps({
                                'runner_id': 'pipeline-123',
                            }),
                        'param':
                            123,
                    })),
        }
    })
    response = self.test_app.post('/push?format=json', params=request_body)
    self.assertEqual(200, response.status_code)

  @mock.patch.object(AsynchronousPipeline, 'from_id', return_value='not-async')
  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testFailedPushDueToPipelineNotAsync(self, *_):
    request_body = json.dumps({
        'message': {
            'message_id':
                'unique-message-id',
            'attributes': {
                'auth_token': 'secret',
            },
            'data':
                base64.b64encode(
                    json.dumps({
                        'user_data':
                            json.dumps({
                                'runner_id': 'pipeline-123',
                            }),
                        'param':
                            123,
                    })),
        }
    })
    response = self.test_app.post('/push?format=json', params=request_body)
    self.assertEqual(200, response.status_code)

  def testFailedPushDueToUnexpectedFormat(self):
    request_body = json.dumps({
        'message': {
            'message_id':
                'unique-message-id',
            'data':
                base64.b64encode(
                    json.dumps({
                        'user_data':
                            json.dumps({
                                'runner_id': 'pipeline-123',
                            }),
                        'param':
                            123,
                    })),
        }
    })
    response = self.test_app.post('/push?format=json', params=request_body)
    self.assertEqual(200, response.status_code)
