# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import unittest

from libs.http.retry_http_client import RetryHttpClient
from common import rpc_util


class RpcUtilTest(unittest.TestCase):

  @mock.patch.object(rpc_util, '_GetResultJson')
  @mock.patch.object(rpc_util, 'DownloadData')
  def testDownloadJsonData(self, mock_fn_1, mock_fn_2):
    mocked_response_json = {'a': 'a'}
    mocked_response = json.dumps(mocked_response_json)
    mock_fn_1.return_value = mocked_response
    mock_fn_2.return_value = mocked_response_json

    url = 'url'
    data = {'data': 'data'}
    http_client = RetryHttpClient()

    response_json = rpc_util.DownloadJsonData(url, data, http_client)

    self.assertEqual(response_json, mocked_response_json)
    mock_fn_1.assert_called_once_with(url, data, http_client)
    mock_fn_2.assert_called_once_with(mocked_response)

  def testDownloadDataError(self):
    mocked_http_client = mock.Mock()
    mocked_http_client.Post.return_value = (404, '404')

    url = 'url'
    data = {'data': 'data'}
    self.assertIsNone(rpc_util.DownloadData(url, data, mocked_http_client))
    mocked_http_client.assert_has_calls(
        mock.call.Post(
            'url',
            json.dumps(data),
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }))

  def testDownloadData(self):
    response = 'response'
    mocked_http_client = mock.Mock()
    mocked_http_client.Post.return_value = (200, response)

    url = 'url'
    data = {'data': 'data'}
    self.assertEqual(response,
                     rpc_util.DownloadData(url, data, mocked_http_client))

  def testGetResultJsonNoPrefix(self):
    response = 'response_json'
    self.assertEqual(response, rpc_util._GetResultJson(response))

  def testGetResultJson(self):
    response_json = 'response_json'
    response = '%s%s' % (rpc_util._RESPONSE_PREFIX, response_json)
    self.assertEqual(response_json, rpc_util._GetResultJson(response))
