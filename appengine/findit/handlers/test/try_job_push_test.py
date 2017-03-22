# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import base64
import json

import mock
import webapp2

from testing_utils import testing

from common.waterfall import pubsub_callback
from handlers.try_job_push import TryJobPush
from model.wf_try_job_data import WfTryJob
from model.wf_try_job_data import WfTryJobData


class TryJobPushTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/pubsub/tryjobpush', TryJobPush),], debug=True)

  def setUp(self):
    super(TryJobPushTest, self).setUp()

  # Send well formed notification for job that does not exist
  @mock.patch('logging.warning')
  def testTryJobPushMissingJob(self, logging_mock):
    self.test_app.post('/pubsub/tryjobpush', params={
        'data': json.dumps({
            'message':{
                'attributes':{
                    'auth_token': pubsub_callback.GetVerificationToken(),
                    'build_id': '12345',
                },
                'data': base64.b64encode(json.dumps({
                    'build_id': '12345',
                    'user_data': json.dumps({
                        'Message-Type': 'BuildbucketStatusChange',
                    }),
                })),
            },
        }),
        'format': 'json',
    })
    self.assertTrue(logging_mock.called)


  # ill formed notification (bad token)
  def testTryJobPushBadToken(self):
    # We expect a 400 error, and a webtest.webtest.AppError (not in path,
    # catching plain Exception)
    with self.assertRaisesRegexp(Exception, '.*400.*'):
      _ = self.test_app.post('/pubsub/tryjobpush', params={
          'data': json.dumps({
              'message':{
                  'attributes':{
                      'auth_token': 'BadTokenString',
                      'build_id': '12345',  # Shouldn't matter
                  },
                  'data': base64.b64encode('Hello World!'), # Shouldn't matter.
              },
          }),
        'format': 'json',
      })

  def testTryJobPushBadFormat(self):
    # We expect a 500 error, and a webtest.webtest.AppError (not in path,
    # catching plain Exception)
    with self.assertRaisesRegexp(Exception, '.*500.*'):
      _ = self.test_app.post('/pubsub/tryjobpush', params={
          'data': json.dumps({
              'message':{
                  'data': base64.b64encode('Hello World!'),
              },
          }),
        'format': 'json',
      })

  # Send notification with unsupported message-type
  def testTryJobPushUnsupportedMessageType(self):
    # We expect a 500 error, and a webtest.webtest.AppError (not in path,
    # catching plain Exception)
    with self.assertRaisesRegexp(Exception, '.*500.*'):
      _ = self.test_app.post('/pubsub/tryjobpush', params={
          'data': json.dumps({
              'message':{
                  'attributes':{
                      'auth_token': pubsub_callback.GetVerificationToken(),
                      'build_id': '8988270260466361040',
                  },
                  'data': base64.b64encode(json.dumps({
                      'build_id': '8988270260466361040',
                      'user_data': json.dumps({
                          # Should break beacause of this
                          'Message-Type': 'HyperLoopSpaceJump',
                      }),
                  })),
              },
          }),
        'format': 'json',
      })

  # Send well formed notification
  def testTryJobPush(self):
    try_job_in_progress = WfTryJobData.Create(12345)
    try_job_in_progress.try_job_key = WfTryJob.Create('m', 'b', 1).key
    try_job_in_progress.try_job_type = 'compile'
    try_job_in_progress.start_time = datetime(2016, 5, 4, 0, 0, 1)
    try_job_in_progress.request_time = datetime(2016, 5, 4, 0, 0, 0)
    try_job_in_progress.try_job_url = 'url1'
    try_job_in_progress.callback_url = '/callback?pipeline_id=f9f89162ef32c7fb7'
    try_job_in_progress.last_buildbucket_response = {'status': 'STARTED'}
    try_job_in_progress.put()

    with mock.patch('google.appengine.api.taskqueue.add') as mock_queue:
      self.test_app.post('/pubsub/tryjobpush', params={
          'data': json.dumps({
              'message':{
                  'attributes':{
                      'auth_token': pubsub_callback.GetVerificationToken(),
                      'build_id': 12345,
                  },
                  'data': base64.b64encode(json.dumps({
                      'build_id': 12345,
                      'user_data': json.dumps({
                          'Message-Type': 'BuildbucketStatusChange',
                      }),
                  })),
              },
          }),
          'format': 'json',
      })
      mock_queue.assert_called_once()

  @mock.patch('logging.warning')
  def testTryJobPushMissingCallback(self, logging_mock):
    try_job_in_progress = WfTryJobData.Create(12345)
    try_job_in_progress.try_job_key = WfTryJob.Create('m', 'b', 1).key
    try_job_in_progress.try_job_type = 'compile'
    try_job_in_progress.start_time = datetime(2016, 5, 4, 0, 0, 1)
    try_job_in_progress.request_time = datetime(2016, 5, 4, 0, 0, 0)
    try_job_in_progress.try_job_url = 'url1'
    # NB That the try_job_data is not associated with a pipeline callback
    try_job_in_progress.last_buildbucket_response = {'status': 'STARTED'}
    try_job_in_progress.put()

    # This should not break, so that pubsub does not keep retrying. We'll only
    # log a message.
    self.test_app.post('/pubsub/tryjobpush', params={
        'data': json.dumps({
            'message':{
                'attributes':{
                    'auth_token': pubsub_callback.GetVerificationToken(),
                    'build_id': 12345,
                },
                'data': base64.b64encode(json.dumps({
                    'build_id': 12345,
                    'user_data': json.dumps({
                        'Message-Type': 'BuildbucketStatusChange',
                    }),
                })),
            },
        }),
        'format': 'json',
    })
    self.assertTrue(logging_mock.called)

  def testTopicExists(self):
    self.assertIsNotNone(pubsub_callback.GetTryJobTopic())
