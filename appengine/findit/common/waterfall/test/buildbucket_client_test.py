# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import mock

from testing_utils import testing

from gae_libs.http import auth_util
from gae_libs.http import http_client_appengine
from common.waterfall import buildbucket_client


_Result = collections.namedtuple('Result',
                                 ['content', 'status_code', 'headers'])


class BuildBucketClientTest(testing.AppengineTestCase):

  def setUp(self):
    super(BuildBucketClientTest, self).setUp()
    self.maxDiff = None

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

  def testTryJobToBuildbucketRequestWithTests(self):
    try_job = buildbucket_client.TryJob('m', 'b', 'r', {'a': '1'}, ['a'], {
        'tests': {
            'a_tests': ['Test.One', 'Test.Two']
        }
    })
    expceted_parameters = {
        'builder_name':
            'b',
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
        'additional_build_parameters': {
            'tests': {
                'a_tests': ['Test.One', 'Test.Two']
            }
        }
    }

    request_json = try_job.ToBuildbucketRequest()
    self.assertEqual('master.m', request_json['bucket'])
    self.assertEqual(2, len(request_json['tags']))
    self.assertEqual('a', request_json['tags'][0])
    self.assertEqual('user_agent:findit', request_json['tags'][1])
    parameters = json.loads(request_json['parameters_json'])
    self.assertEqual(expceted_parameters, parameters)

  def testTryJobToSwarmbucketRequest(self):
    try_job = buildbucket_client.TryJob('luci.c', 'b', 'r', {'a': '1'}, ['a'], {
        'tests': {
            'a_tests': ['Test.One', 'Test.Two'],
        }
    }, 'builder_abc123')
    expceted_parameters = {
        'builder_name':
            'b',
        'changes': [
            {
                'author': {
                    'email': buildbucket_client._ROLE_EMAIL,
                },
                'revision': 'r',
            },
        ],
        'swarming': {
            'override_builder_cfg': {
                'caches': [{
                    'name': 'builder_abc123',
                    'path': 'builder'
                }],
            }
        },
        'properties': {
            'a': '1',
        },
        'additional_build_parameters': {
            'tests': {
                'a_tests': ['Test.One', 'Test.Two']
            }
        }
    }

    request_json = try_job.ToBuildbucketRequest()
    self.assertEqual('luci.c', request_json['bucket'])
    self.assertEqual(2, len(request_json['tags']))
    self.assertEqual('a', request_json['tags'][0])
    self.assertEqual('user_agent:findit', request_json['tags'][1])
    parameters = json.loads(request_json['parameters_json'])
    self.assertEqual(expceted_parameters, parameters)

  def testTryJobToSwarmbucketRequestWithOverrides(self):
    try_job = buildbucket_client.TryJob('luci.c', 'b', 'r', {
        'a': '1',
        'recipe': 'b'
    }, ['a'], {'tests': {
        'a_tests': ['Test.One', 'Test.Two'],
    }}, 'builder_abc123', ['os:Linux'])
    expceted_parameters = {
        'builder_name':
            'b',
        'changes': [
            {
                'author': {
                    'email': buildbucket_client._ROLE_EMAIL,
                },
                'revision': 'r',
            },
        ],
        'swarming': {
            'override_builder_cfg': {
                'caches': [{
                    'name': 'builder_abc123',
                    'path': 'builder'
                }],
                'dimensions': ['os:Linux'],
                'recipe': {
                    'name': 'b'
                }
            }
        },
        'properties': {
            'a': '1',
            'recipe': 'b'
        },
        'additional_build_parameters': {
            'tests': {
                'a_tests': ['Test.One', 'Test.Two']
            }
        }
    }

    request_json = try_job.ToBuildbucketRequest()
    self.assertEqual('luci.c', request_json['bucket'])
    self.assertEqual(2, len(request_json['tags']))
    self.assertEqual('a', request_json['tags'][0])
    self.assertEqual('user_agent:findit', request_json['tags'][1])
    parameters = json.loads(request_json['parameters_json'])
    self.assertEqual(expceted_parameters, parameters)

  def testTryJobToBuildbucketRequestWithRevision(self):
    try_job = buildbucket_client.TryJob('m', 'b', 'r', {'a': '1'}, ['a'], {})
    expceted_parameters = {
        'builder_name':
            'b',
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
    try_job = buildbucket_client.TryJob('m', 'b', None, {'a': '1'}, ['a'], {})
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

  @mock.patch.object(buildbucket_client.auth_util, 'GetAuthToken',
                     return_value='token')
  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testTriggerTryJobsSuccess(self, mocked_fetch, _):
    response = {
        'build': {
            'id': '1',
            'url': 'url',
            'status': 'SCHEDULED',
        }
    }
    try_job = buildbucket_client.TryJob('m', 'b', 'r', {'a': 'b'}, [], {})
    mocked_fetch.return_value = _Result(
        status_code=200, content=json.dumps(response), headers={})
    results = buildbucket_client.TriggerTryJobs([try_job])
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNone(error)
    self.assertIsNotNone(build)
    self.assertEqual('1', build.id)
    self.assertEqual('url', build.url)
    self.assertEqual('SCHEDULED', build.status)

  @mock.patch.object(buildbucket_client.auth_util, 'GetAuthToken',
                     return_value='token')
  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testTriggerTryJobsFailure(self, mocked_fetch, _):
    response = {
        'error': {
            'reason': 'error',
            'message': 'message',
        }
    }
    try_job = buildbucket_client.TryJob('m', 'b', 'r', {}, [], {})
    mocked_fetch.return_value = _Result(
        status_code=200, content=json.dumps(response), headers={})
    results = buildbucket_client.TriggerTryJobs([try_job])
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNotNone(error)
    self.assertEqual('error', error.reason)
    self.assertEqual('message', error.message)
    self.assertIsNone(build)

  @mock.patch.object(buildbucket_client.auth_util, 'GetAuthToken',
                     return_value='token')
  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testTriggerTryJobsRequestFailure(self, mocked_fetch, _):
    response = 'Not Found'
    try_job = buildbucket_client.TryJob('m', 'b', 'r', {}, [], {})
    mocked_fetch.return_value = _Result(
        status_code=404, content=response, headers={})
    results = buildbucket_client.TriggerTryJobs([try_job])
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNotNone(error)
    self.assertEqual(404, error.reason)
    self.assertEqual('Not Found', error.message)
    self.assertIsNone(build)

  @mock.patch.object(buildbucket_client.auth_util, 'GetAuthToken',
                     return_value='token')
  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testGetTryJobsSuccess(self, mocked_fetch, _):
    response = {'build': {'id': '1', 'url': 'url', 'status': 'STARTED'}}
    mocked_fetch.return_value = _Result(
        status_code=200, content=json.dumps(response), headers={})
    results = buildbucket_client.GetTryJobs(['1'])
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNone(error)
    self.assertIsNotNone(build)
    self.assertEqual('1', build.id)
    self.assertEqual('url', build.url)
    self.assertEqual('STARTED', build.status)

  @mock.patch.object(buildbucket_client.auth_util, 'GetAuthToken',
                     return_value='token')
  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testGetTryJobsFailure(self, mocked_fetch, _):
    response = {
        'error': {
            'reason': 'BUILD_NOT_FOUND',
            'message': 'message',
        }
    }
    mocked_fetch.return_value = _Result(
        status_code=200, content=json.dumps(response), headers={})
    results = buildbucket_client.GetTryJobs(['2'])
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNotNone(error)
    self.assertEqual('BUILD_NOT_FOUND', error.reason)
    self.assertEqual('message', error.message)
    self.assertIsNone(build)

  @mock.patch.object(buildbucket_client.auth_util, 'GetAuthToken',
                     return_value='token')
  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testGetTryJobsRequestFailure(self, mocked_fetch, _):
    response = 'Not Found'
    mocked_fetch.return_value = _Result(
        status_code=404, content=response, headers={})
    results = buildbucket_client.GetTryJobs(['3'])
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNotNone(error)
    self.assertEqual(404, error.reason)
    self.assertEqual('Not Found', error.message)
    self.assertIsNone(build)
