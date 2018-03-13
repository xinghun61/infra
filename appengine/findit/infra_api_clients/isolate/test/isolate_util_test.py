# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import mock
import zlib

from infra_api_clients import http_client_util
from infra_api_clients.isolate import isolate_util
from waterfall.test import wf_testcase


class IsolateUtilTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(http_client_util, 'SendRequestToServer')
  def testFetchFileFromIsolatedServer(self, mock_fn):
    needed_content = json.dumps({'files': {'output.json': {'h': 'h'}}})
    content = json.dumps({
        'content': base64.b64encode(zlib.compress(needed_content)),
        'kind': 'isolateservice#resourcesItem',
        'etag': '\'H_l3X6I4W5tDAoEMN5F54pK9RCg/teAVzABomW_XpYoLaFFl293qArc\''
    })
    mock_fn.return_value = (content, None)
    self.assertEqual((needed_content, None),
                     isolate_util.FetchFileFromIsolatedServer(
                         'shard1_isolated', 'default-gzip', 'isolated_server',
                         None))

  @mock.patch.object(
      http_client_util, 'SendRequestToServer', return_value=(None, {
          'code': 1
      }))
  def testFetchFileFromIsolatedServerError(self, *_):
    self.assertEqual((None, {
        'code': 1
    }),
                     isolate_util.FetchFileFromIsolatedServer(
                         'shard1_isolated', 'default-gzip', 'isolated_server',
                         None))

  @mock.patch.object(http_client_util, 'SendRequestToServer')
  def testFetchFileFromIsolatedServerFromUrl(self, mock_request):
    content_with_url = json.dumps({
        'url': 'url',
        'kind': 'isolateservice#resourcesItem',
        'etag': '\'H_l3X6I4W5tDAoEMN5F54pK9RCg/teAVzABomW_XpYoLaFFl293qArc\''
    })
    content = zlib.compress('content')

    mock_request.side_effect = [(content_with_url, None), (content, None)]

    result, error = isolate_util.FetchFileFromIsolatedServer(
        'shard1_isolated', 'default-gzip', 'isolated_server', None)

    self.assertEqual('content', result)
    self.assertIsNone(error)
