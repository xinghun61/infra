# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from testing_utils import testing

from common import buildbucket_client
from components import net


class _DeferredResult(object):
  def __init__(self, result):
    self._result = result

  def get_result(self):
    return self._result


class BuilcBucketClientTest(testing.AppengineTestCase):
  def testGetBucketName(self):
    mapping = {
        'a': 'master.a',
        'master.b': 'master.b',
    }
    for master_name, expected_full_master_name in mapping.iteritems():
      self.assertEqual(expected_full_master_name,
                       buildbucket_client._GetBucketName(master_name))

  def testTryJobToBuildbucketRequestWithRevision(self):
    try_job = buildbucket_client.TryJob('m', 'b', 'r', {'a': '1'}, ['a'])
    expceted_parameters = {
        'builder_name': 'b',
        'changes': [
            {
                'author': {
                    'email': buildbucket_client._ROLE_EMAIL,
                },
                'revision': 'r',
            },
        ],
        'properties': {
            'a': '1',
        },
    }

    request_json = try_job.ToBuildbucketRequest()
    self.assertEqual('master.m', request_json['bucket'])
    self.assertEqual(2, len(request_json['tags']))
    self.assertEqual('a', request_json['tags'][0])
    self.assertEqual('user_agent:findit', request_json['tags'][1])
    parameters = json.loads(request_json['parameters_json'])
    self.assertEqual(expceted_parameters, parameters)

  def testTryJobToBuildbucketRequestWithoutRevision(self):
    try_job = buildbucket_client.TryJob('m', 'b', None, {'a': '1'}, ['a'])
    expceted_parameters = {
        'builder_name': 'b',
        'properties': {
            'a': '1',
        },
    }

    request_json = try_job.ToBuildbucketRequest()
    self.assertEqual('master.m', request_json['bucket'])
    self.assertEqual(2, len(request_json['tags']))
    self.assertEqual('a', request_json['tags'][0])
    self.assertEqual('user_agent:findit', request_json['tags'][1])
    parameters = json.loads(request_json['parameters_json'])
    self.assertEqual(expceted_parameters, parameters)

  def _Mock_json_request_async_for_put(self, requests, responses):
    def Mocked_json_request_async(
       url, method=None, payload=None, scopes=None, *_, **__):
      self.assertEqual(buildbucket_client._BUILDBUCKET_PUT_GET_ENDPOINT, url)
      self.assertEqual('PUT', method)
      self.assertEqual(net.EMAIL_SCOPE, scopes)
      requests.append(payload)
      return _DeferredResult(responses.pop())
    self.mock(net, 'json_request_async', Mocked_json_request_async)

  def testTriggerTryJobsSuccess(self):
    requests = []
    responses = [
        {
          'build': {
              'id': '1',
              'url': 'url',
              'status': 'SCHEDULED',
          }
        }
    ]
    self._Mock_json_request_async_for_put(requests, responses)
    try_job = buildbucket_client.TryJob('m', 'b', 'r', {'a': 'b'}, [])
    results = buildbucket_client.TriggerTryJobs([try_job])
    self.assertEqual(1, len(requests))
    self.assertEqual(requests[0], try_job.ToBuildbucketRequest())
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNone(error)
    self.assertIsNotNone(build)
    self.assertEqual('1', build.id)
    self.assertEqual('url', build.url)
    self.assertEqual('SCHEDULED', build.status)

  def testTriggerTryJobsFailure(self):
    requests = []
    responses = [
        {
          'error': {
              'reason': 'error',
              'message': 'message',
          }
        }
    ]
    self._Mock_json_request_async_for_put(requests, responses)
    try_job = buildbucket_client.TryJob('m', 'b', 'r', {}, [])
    results = buildbucket_client.TriggerTryJobs([try_job])
    self.assertEqual(1, len(requests))
    self.assertEqual(requests[0], try_job.ToBuildbucketRequest())
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNotNone(error)
    self.assertEqual('error', error.reason)
    self.assertEqual('message', error.message)
    self.assertIsNone(build)

  def _Mock_json_request_async_for_get(self):
    def Mocked_json_request_async(url, method=None, scopes=None, *_, **__):
      url,  build_id = url.rsplit('/', 1)
      self.assertEqual(buildbucket_client._BUILDBUCKET_PUT_GET_ENDPOINT, url)
      self.assertEqual('GET', method)
      self.assertEqual(net.EMAIL_SCOPE, scopes)
      data = {
          '1': {
              'build': {
                  'id': '1',
                  'url': 'url',
                  'status': 'STARTED',
              }
          },
          '2': {
              'error': {
                  'reason': 'BUILD_NOT_FOUND',
                  'message': 'message',
              }
          }
      }
      return _DeferredResult(data.get(build_id))
    self.mock(net, 'json_request_async', Mocked_json_request_async)

  def testGetTryJobsSuccess(self):
    self._Mock_json_request_async_for_get()
    results = buildbucket_client.GetTryJobs(['1'])
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNone(error)
    self.assertIsNotNone(build)
    self.assertEqual('1', build.id)
    self.assertEqual('url', build.url)
    self.assertEqual('STARTED', build.status)

  def testGetTryJobsFailure(self):
    self._Mock_json_request_async_for_get()
    results = buildbucket_client.GetTryJobs(['2'])
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNotNone(error)
    self.assertEqual('BUILD_NOT_FOUND', error.reason)
    self.assertEqual('message', error.message)
    self.assertIsNone(build)
