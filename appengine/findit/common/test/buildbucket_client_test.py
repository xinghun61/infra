# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from testing_utils import testing

from common import buildbucket_client


class BuildBucketClientTest(testing.AppengineTestCase):
  def setUp(self):
    super(BuildBucketClientTest, self).setUp()
    self.auth_token = '2234567'

    with self.mock_urlfetch() as urlfetch:
      self.mocked_urlfetch = urlfetch

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

  def _MockUrlFetch(self, build_id, try_job_request, content, status_code=200):
    base_url = (
        'https://cr-buildbucket.appspot.com/_ah/api/buildbucket/v1/builds')
    headers = {
        'Content-Type': 'application/json; charset=UTF-8'
    }
    if build_id:
      url = base_url + '/' + build_id
      self.mocked_urlfetch.register_handler(
          url, content, status_code=status_code, headers=headers)
    else:
      self.mocked_urlfetch.register_handler(
          base_url, content, status_code=status_code,
          headers=headers, data=try_job_request)

  def testTriggerTryJobsSuccess(self):
    response = {
      'build': {
          'id': '1',
          'url': 'url',
          'status': 'SCHEDULED',
      }
    }
    try_job = buildbucket_client.TryJob('m', 'b', 'r', {'a': 'b'}, [])
    self._MockUrlFetch(
        None, json.dumps(try_job.ToBuildbucketRequest()), json.dumps(response))
    results = buildbucket_client.TriggerTryJobs([try_job], self.auth_token)
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNone(error)
    self.assertIsNotNone(build)
    self.assertEqual('1', build.id)
    self.assertEqual('url', build.url)
    self.assertEqual('SCHEDULED', build.status)

  def testTriggerTryJobsFailure(self):
    response = {
      'error': {
          'reason': 'error',
          'message': 'message',
      }
    }
    try_job = buildbucket_client.TryJob('m', 'b', 'r', {}, [])
    self._MockUrlFetch(
        None, json.dumps(try_job.ToBuildbucketRequest()), json.dumps(response))
    results = buildbucket_client.TriggerTryJobs([try_job], self.auth_token)
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNotNone(error)
    self.assertEqual('error', error.reason)
    self.assertEqual('message', error.message)
    self.assertIsNone(build)

  def testTriggerTryJobsRequestFailure(self):
    response = 'Not Found'
    try_job = buildbucket_client.TryJob('m', 'b', 'r', {}, [])
    self._MockUrlFetch(
        None, json.dumps(try_job.ToBuildbucketRequest()),
        response, 404)
    results = buildbucket_client.TriggerTryJobs([try_job], self.auth_token)
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNotNone(error)
    self.assertEqual(404, error.reason)
    self.assertEqual('Not Found', error.message)
    self.assertIsNone(build)

  def testGetTryJobsSuccess(self):
    response = {
        'build': {
            'id': '1',
            'url': 'url',
            'status': 'STARTED',
            'result_details_json':(
                '{"properties": {"result": [["rev1", "passed"],'
                ' ["rev2", "failed"]]}}')
        }
    }
    self._MockUrlFetch(
        '1', None, json.dumps(response))
    results = buildbucket_client.GetTryJobs(['1'], self.auth_token)
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNone(error)
    self.assertIsNotNone(build)
    self.assertEqual('1', build.id)
    self.assertEqual('url', build.url)
    self.assertEqual('STARTED', build.status)

    expected_result = [
        ['rev1', 'passed'],
        ['rev2', 'failed']
    ]
    self.assertEqual(expected_result, build.result)

  def testGetTryJobsFailure(self):
    response = {
        'error': {
            'reason': 'BUILD_NOT_FOUND',
            'message': 'message',
        }
    }
    self._MockUrlFetch(
        '2', None, json.dumps(response))
    results = buildbucket_client.GetTryJobs(['2'], self.auth_token)
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNotNone(error)
    self.assertEqual('BUILD_NOT_FOUND', error.reason)
    self.assertEqual('message', error.message)
    self.assertIsNone(build)

  def testGetTryJobsRequestFailure(self):
    response = 'Not Found'
    self._MockUrlFetch(
        '3', None, response, 404)
    results = buildbucket_client.GetTryJobs(['3'], self.auth_token)
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNotNone(error)
    self.assertEqual(404, error.reason)
    self.assertEqual('Not Found', error.message)
    self.assertIsNone(build)
