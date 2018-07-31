# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import mock

from buildbucket_proto.build_pb2 import Build
from testing_utils import testing

from gae_libs.http import http_client_appengine
from common.findit_http_client import FinditHttpClient
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
    try_job = buildbucket_client.TryJob(
        'm', 'b', {'a': '1'}, ['a'],
        {'tests': {
            'a_tests': ['Test.One', 'Test.Two']
        }})
    expceted_parameters = {
        'builder_name': 'b',
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
    try_job = buildbucket_client.TryJob(
        'luci.c', 'b', {'a': '1'}, ['a'],
        {'tests': {
            'a_tests': ['Test.One', 'Test.Two'],
        }}, 'builder_abc123')
    expceted_parameters = {
        'builder_name': 'b',
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
    try_job = buildbucket_client.TryJob(
        'luci.c',
        'b', {
            'a': '1',
            'recipe': 'b'
        }, ['a'], {'tests': {
            'a_tests': ['Test.One', 'Test.Two'],
        }},
        'builder_abc123', ['os:Linux'],
        priority=1)
    expceted_parameters = {
        'builder_name': 'b',
        'swarming': {
            'override_builder_cfg': {
                'caches': [{
                    'name': 'builder_abc123',
                    'path': 'builder'
                }],
                'dimensions': ['os:Linux'],
                'recipe': {
                    'name': 'b'
                },
                'priority': 1
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

  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testTriggerTryJobsSuccess(self, mocked_fetch):
    response = {
        'build': {
            'id': '1',
            'url': 'url',
            'status': 'SCHEDULED',
        }
    }
    try_job = buildbucket_client.TryJob('m', 'b', {'a': 'b'}, [], {})
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

  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testTriggerTryJobsFailure(self, mocked_fetch):
    response = {
        'error': {
            'reason': 'error',
            'message': 'message',
        }
    }
    try_job = buildbucket_client.TryJob('m', 'b', {}, [], {})
    mocked_fetch.return_value = _Result(
        status_code=200, content=json.dumps(response), headers={})
    results = buildbucket_client.TriggerTryJobs([try_job])
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNotNone(error)
    self.assertEqual('error', error.reason)
    self.assertEqual('message', error.message)
    self.assertIsNone(build)

  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testTriggerTryJobsRequestFailure(self, mocked_fetch):
    response = 'Not Found'
    try_job = buildbucket_client.TryJob('m', 'b', {}, [], {})
    mocked_fetch.return_value = _Result(
        status_code=404, content=response, headers={})
    results = buildbucket_client.TriggerTryJobs([try_job])
    self.assertEqual(1, len(results))
    error, build = results[0]
    self.assertIsNotNone(error)
    self.assertEqual(404, error.reason)
    self.assertEqual('Not Found', error.message)
    self.assertIsNone(build)

  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testGetTryJobsSuccess(self, mocked_fetch):
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

  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testGetTryJobsFailure(self, mocked_fetch):
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

  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testGetTryJobsRequestFailure(self, mocked_fetch):
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

  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testSearchBuildsSuccess(self, mocked_fetch):
    tags = [('tag', 'builder:Linux Test')]
    response = {'builds': [{'status': 'COMPLETED'}]}
    mocked_fetch.return_value = _Result(
        status_code=200, content=json.dumps(response), headers={})
    self.assertEqual(response, buildbucket_client.SearchBuilds(tags))

  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testSearchBuildsFailed(self, mocked_fetch):
    tags = [('tag', 'builder:Linux Test')]
    response = 'Not Found'
    mocked_fetch.return_value = _Result(
        status_code=404, content=response, headers={})
    self.assertIsNone(buildbucket_client.SearchBuilds(tags))

  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testSearchBuildsResponseNotJsonSerializable(self, mocked_fetch):
    tags = [('tag', 'builder:Linux Test')]
    response = 'Not json serializable.'
    mocked_fetch.return_value = _Result(
        status_code=200, content=response, headers={})
    self.assertIsNone(buildbucket_client.SearchBuilds(tags))

  @mock.patch.object(FinditHttpClient, 'Post')
  def testGetV2Build(self, mock_post):
    mock_build = Build()
    mock_build.id = 8945610992972640896
    mock_build.status = 12
    mock_build.output.properties['mastername'] = 'chromium.linux'
    mock_build.output.properties['buildername'] = 'Linux Builder'
    mock_build.output.properties.get_or_create_struct(
        'swarm_hashes_ref/heads/mockmaster(at){#123}')[
            'mock_target'] = 'mock_hash'
    gitiles_commit = mock_build.input.gitiles_commit
    gitiles_commit.host = 'gitiles.host'
    gitiles_commit.project = 'gitiles/project'
    gitiles_commit.ref = 'refs/heads/mockmaster'
    mock_build.builder.project = 'mock_luci_project'
    mock_build.builder.bucket = 'mock_bucket'
    mock_build.builder.builder = 'Linux Builder'
    mock_headers = {'X-Prpc-Grpc-Code': '0'}
    binary_data = mock_build.SerializeToString()
    mock_post.return_value = (200, binary_data, mock_headers)
    build = buildbucket_client.GetV2Build(8945610992972640896)
    self.assertIsNotNone(build)
    self.assertEqual(mock_build.id, build.id)

    mock_headers = {'X-Prpc-Grpc-Code': '4'}
    binary_data = mock_build.SerializeToString()
    mock_post.return_value = (404, binary_data, mock_headers)
    self.assertIsNone(buildbucket_client.GetV2Build(8945610992972640896))

  @mock.patch.object(FinditHttpClient, 'Post')
  def testGetBuildNumberFromBuildId(self, mock_post):
    build_id = 10000
    expected_build_number = 12345
    mock_build = Build()
    mock_build.id = build_id
    mock_build.status = 12
    mock_build.output.properties['mastername'] = 'chromium.linux'
    mock_build.output.properties['buildername'] = 'Linux Builder'
    mock_build.output.properties['buildnumber'] = expected_build_number
    mock_build.output.properties.get_or_create_struct(
        'swarm_hashes_ref/heads/mockmaster(at){#123}')[
            'mock_target'] = 'mock_hash'
    gitiles_commit = mock_build.input.gitiles_commit
    gitiles_commit.host = 'gitiles.host'
    gitiles_commit.project = 'gitiles/project'
    gitiles_commit.ref = 'refs/heads/mockmaster'
    mock_build.builder.project = 'mock_luci_project'
    mock_build.builder.bucket = 'mock_bucket'
    mock_build.builder.builder = 'Linux Builder'
    mock_headers = {'X-Prpc-Grpc-Code': '0'}
    binary_data = mock_build.SerializeToString()
    mock_post.return_value = (200, binary_data, mock_headers)

    self.assertEqual(expected_build_number,
                     buildbucket_client.GetBuildNumberFromBuildId(build_id))
