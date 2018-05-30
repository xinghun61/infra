# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import unittest

from infra_api_clients import crrev
from libs.http.retry_http_client import RetryHttpClient


class CrrevTest(unittest.TestCase):

  @mock.patch.object(RetryHttpClient, 'Get', return_value=(404, 'error', {}))
  def testHttpRequestFailure(self, mocked_Get):
    http_client = RetryHttpClient()
    self.assertIsNone(crrev.RedirectByCommitPosition(http_client, 5000))
    mocked_Get.assert_called_once_with(
        'https://cr-rev.appspot.com/_ah/api/crrev/v1/redirect/5000')

  @mock.patch.object(
      RetryHttpClient,
      'Get',
      return_value=(200,
                    json.dumps({
                        'git_sha': 'sha',
                        'repo_url': 'url',
                        'key': 'value'
                    }), {}))
  def testHttpRequestSuccess(self, mocked_Get):
    http_client = RetryHttpClient()
    expected_result = {
        'git_sha': 'sha',
        'repo_url': 'url',
    }
    self.assertDictEqual(expected_result,
                         crrev.RedirectByCommitPosition(http_client, 5000))
    mocked_Get.assert_called_once_with(
        'https://cr-rev.appspot.com/_ah/api/crrev/v1/redirect/5000')
