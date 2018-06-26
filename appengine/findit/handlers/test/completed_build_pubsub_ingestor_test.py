# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import mock

import webapp2
import webtest

from google.protobuf.struct_pb2 import Struct

from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.common_pb2 import GitilesCommit
from testing_utils.testing import AppengineTestCase

from common.findit_http_client import FinditHttpClient
from handlers import completed_build_pubsub_ingestor
from model.isolated_target import IsolatedTarget


class CompletedBuildPubsubIngestorTest(AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/index-isolated-builds',
           completed_build_pubsub_ingestor.CompletedBuildPubsubIngestor),
      ],
      debug=True)

  @mock.patch.object(FinditHttpClient, 'Post')
  def testSucessfulPushCIBuild(self, mock_post):
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

    request_body = json.dumps({
        'message': {
            'attributes': {
                'build_id': str(mock_build.id),
            },
            'data':
                base64.b64encode(
                    json.dumps({
                        'build': {
                            'project': 'chromium',
                            'status': 'COMPLETED'
                        }
                    })),
        },
    })
    response = self.test_app.post(
        '/index-isolated-builds?format=json', params=request_body)
    self.assertEqual(200, response.status_int)
    self.assertEqual(123, IsolatedTarget.Get('mock_hash').commit_position)
    self.assertEqual(8945610992972640896,
                     IsolatedTarget.Get('mock_hash').build_id)
    self.assertEqual(1, len(json.loads(response.body)['created_rows']))

  @mock.patch.object(FinditHttpClient, 'Post')
  def testPushNoBuild(self, mock_post):
    mock_headers = {'X-Prpc-Grpc-Code': '5'}
    mock_post.return_value = (404, 'Build not found', mock_headers)

    request_body = json.dumps({
        'message': {
            'attributes': {
                'build_id': '123456',
            },
            'data':
                base64.b64encode(
                    json.dumps({
                        'build': {
                            'project': 'chromium',
                            'status': 'COMPLETED'
                        }
                    })),
        },
    })
    response = self.test_app.post(
        '/index-isolated-builds?format=json', params=request_body, status=404)
    self.assertEqual(404, response.status_int)

  @mock.patch.object(FinditHttpClient, 'Post')
  def testPushPendingBuild(self, mock_post):
    request_body = json.dumps({
        'message': {
            'attributes': {
                'build_id': '123456',
            },
            'data':
                base64.b64encode(
                    json.dumps({
                        'build': {
                            'project': 'chromium',
                            'status': 'PENDING'
                        }
                    })),
        },
    })
    response = self.test_app.post(
        '/index-isolated-builds?format=json', params=request_body)
    self.assertFalse(mock_post.called)
    self.assertEqual(200, response.status_int)

  @mock.patch.object(FinditHttpClient, 'Post')
  def testSucessfulPushBadFormat(self, mock_post):
    request_body = json.dumps({
        'message': {},
    })
    response = self.test_app.post(
        '/index-isolated-builds?format=json', params=request_body)
    self.assertFalse(mock_post.called)
    self.assertEqual(200, response.status_int)

  @mock.patch.object(FinditHttpClient, 'Post')
  def testNonIsolateBuild(self, mock_post):
    # This build does not isolate any targets.
    mock_build = Build()
    mock_build.id = 8945610992972640896
    mock_build.status = 12
    mock_build.output.properties['mastername'] = 'chromium.linux'
    mock_build.output.properties['buildername'] = 'Linux Tester'
    gitiles_commit = mock_build.input.gitiles_commit
    gitiles_commit.host = 'gitiles.host'
    gitiles_commit.project = 'gitiles/project'
    gitiles_commit.ref = 'refs/heads/mockmaster'
    mock_build.builder.project = 'mock_luci_project'
    mock_build.builder.bucket = 'mock_bucket'
    mock_build.builder.builder = 'Linux Tester'
    mock_headers = {'X-Prpc-Grpc-Code': '0'}
    binary_data = mock_build.SerializeToString()
    mock_post.return_value = (200, binary_data, mock_headers)

    request_body = json.dumps({
        'message': {
            'attributes': {
                'build_id': str(mock_build.id),
            },
            'data':
                base64.b64encode(
                    json.dumps({
                        'build': {
                            'project': 'chromium',
                            'status': 'COMPLETED'
                        }
                    })),
        },
    })
    response = self.test_app.post(
        '/index-isolated-builds?format=json', params=request_body)
    self.assertEqual(200, response.status_int)
    self.assertNotIn('created_rows', response.body)

  @mock.patch.object(FinditHttpClient, 'Post')
  def testNoMasternameBuild(self, mock_post):
    mock_build = Build()
    mock_build.id = 8945610992972640896
    mock_build.status = 12
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

    request_body = json.dumps({
        'message': {
            'attributes': {
                'build_id': str(mock_build.id),
            },
            'data':
                base64.b64encode(
                    json.dumps({
                        'build': {
                            'project': 'chromium',
                            'status': 'COMPLETED'
                        }
                    })),
        },
    })
    response = self.test_app.post(
        '/index-isolated-builds?format=json', params=request_body)
    self.assertEqual(200, response.status_int)
    self.assertNotIn('created_rows', response.body)

  @mock.patch.object(FinditHttpClient, 'Post')
  def testSucessfulPushTryJob(self, mock_post):
    mock_build = Build()
    mock_build.id = 8945610992972640896
    mock_build.status = 12
    mock_build.output.properties['mastername'] = 'luci.chromium.findit'
    mock_build.output.properties['buildername'] = ('findit_variable')
    mock_build.output.properties['target_mastername'] = 'chromium.linux'
    mock_build.output.properties['target_buildername'] = (
        'linux_chromium_compile_dbg_ng')
    mock_build.output.properties.get_or_create_struct(
        'swarm_hashes_ref/heads/mockmaster(at){#123}_with_patch')[
            'mock_target'] = 'mock_hash'
    mock_build.output.properties.get_or_create_struct(
        'swarm_hashes_ref/heads/mockmaster(at){#123}_without_patch')[
            'mock_target'] = 'mock_hash_without'
    mock_build.output.properties['repository'] = (
        'https://test.googlesource.com/team/project.git')
    mock_build.output.properties['gitiles_ref'] = 'refs/heads/mockmaster'
    mock_change = mock_build.input.gerrit_changes.add()
    mock_change.host = 'mock.gerrit.host'
    mock_change.change = 12345
    mock_change.patchset = 1
    mock_build.builder.project = 'mock_luci_project'
    mock_build.builder.bucket = 'mock_bucket'
    mock_build.builder.builder = 'findit_variable'
    mock_headers = {'X-Prpc-Grpc-Code': '0'}
    binary_data = mock_build.SerializeToString()
    mock_post.return_value = (200, binary_data, mock_headers)

    request_body = json.dumps({
        'message': {
            'attributes': {
                'build_id': str(mock_build.id),
            },
            'data':
                base64.b64encode(
                    json.dumps({
                        'build': {
                            'project': 'chromium',
                            'status': 'COMPLETED'
                        }
                    })),
        },
    })
    response = self.test_app.post(
        '/index-isolated-builds?format=json', params=request_body)
    self.assertEqual(200, response.status_int)
    self.assertEqual(123, IsolatedTarget.Get('mock_hash').commit_position)
    self.assertEqual(2, len(json.loads(response.body)['created_rows']))

    # Ensure target values were used.
    entry = IsolatedTarget.Get('mock_hash')
    self.assertEqual('chromium.linux', entry.master_name)
    self.assertEqual('linux_chromium_compile_dbg_ng', entry.builder_name)

  @mock.patch.object(FinditHttpClient, 'Post')
  def testPushIgnoreV2Push(self, mock_post):
    request_body = json.dumps({
        'message': {
            'attributes': {
                'build_id': '123456',
                'version': 'v2',
            },
            'data':
                base64.b64encode(
                    json.dumps({
                        'build': {
                            'project': 'chromium',
                            'status': 'COMPLETED'
                        }
                    })),
        },
    })
    response = self.test_app.post(
        '/index-isolated-builds?format=json', params=request_body)
    self.assertFalse(mock_post.called)
    self.assertEqual(200, response.status_int)
