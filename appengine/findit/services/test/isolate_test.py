# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import mock
import zlib

from infra_api_clients import http_client_util
from infra_api_clients.isolate import isolate_util
from services import isolate
from waterfall.test import wf_testcase


def _SimulateContent(d, encoded=False):
  content = zlib.compress(json.dumps(d))
  if encoded:
    content = base64.b64encode(content)
  return content


class IsolateTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(IsolateTest, self).setUp()
    self.content1 = json.dumps({
        'content':
            _SimulateContent(
                {
                    'files': {
                        'output.json': {
                            'h': 'h'
                        }
                    }
                }, encoded=True),
        'kind':
            'isolateservice#resourcesItem',
        'etag':
            '\'H_l3X6I4W5tDAoEMN5F54pK9RCg/teAVzABomW_XpYoLaFFl293qArc\''
    })
    self.content2 = json.dumps({
        'url': 'url',
        'kind': 'isolateservice#resourcesItem',
        'etag': '\'H_l3X6I4W5tDAoEMN5F54pK9RCg/teAVzABomW_XpYoLaFFl293qArc\''
    })

  @mock.patch.object(http_client_util, 'SendRequestToServer')
  def testDownloadFileFromIsolatedServer(self, mock_request):
    isolated_data = {
        'digest': 'shard1_isolated',
        'namespace': 'default-gzip',
        'isolatedserver': 'isolated_server'
    }

    expected_result = {'items': [{'name': 'task'}]}
    content3 = _SimulateContent(expected_result)

    mock_request.side_effect = [(self.content1, None), (self.content2, None),
                                (content3, None)]

    result, error = isolate.DownloadFileFromIsolatedServer(
        isolated_data, None, 'output.json')

    self.assertEqual(expected_result, json.loads(result))
    self.assertIsNone(error)

  @mock.patch.object(
      http_client_util, 'SendRequestToServer', return_value=(None, {
          'code': 1
      }))
  def testDownloadFileFromIsolatedServerFailedToGetMapping(self, _):
    isolated_data = {
        'digest': 'not found',
        'namespace': 'default-gzip',
        'isolatedserver': 'isolated_server'
    }

    result, error = isolate.DownloadFileFromIsolatedServer(
        isolated_data, None, None)

    self.assertIsNone(result)
    self.assertIsNotNone(error)

  @mock.patch.object(http_client_util, 'SendRequestToServer')
  def testDownloadFileFromIsolatedServerFailedGettingFile(self, mock_request):
    isolated_data = {
        'digest': 'shard1_isolated',
        'namespace': 'default-gzip',
        'isolatedserver': 'isolated_server'
    }
    mock_request.side_effect = [(self.content1, None), (None, {'code': 2000})]
    result, error = isolate.DownloadFileFromIsolatedServer(
        isolated_data, None, 'output.json')

    self.assertIsNone(result)
    self.assertEqual({'code': 2000}, error)

  @mock.patch.object(
      isolate_util,
      'FetchFileFromIsolatedServer',
      return_value=(json.dumps({
          'files': {}
      }), None))
  def testGetIsolatedOuptputFileToHashMapNoFiles(self, mock_fn):
    mapping, error = isolate.GetIsolatedOuptputFileToHashMap(
        'digest', 'gzip', 'isolated_server', None)
    self.assertIsNone(mapping)
    self.assertEqual({
        'code': 310,
        'message': 'No files in isolated response'
    }, error.ToSerializable())
    mock_fn.assert_called_once_with('digest', 'gzip', 'isolated_server', None)
