# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.findit_http_client import FinditHttpClient
from infra_api_clients import http_client_util
from waterfall.test import wf_testcase


class HttpClientUtilTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(FinditHttpClient, 'Get')
  def testSendRequestToServerSucceed(self, mocked_get):
    mocked_get.return_value = (200, 'content', {})
    content, error = http_client_util.SendRequestToServer(
        'http://www.someurl.com', FinditHttpClient())
    self.assertEqual(content, 'content')
    self.assertIsNone(error)

  @mock.patch.object(FinditHttpClient, 'Post')
  def testSendRequestToServerRetryTimeout(self, mocked_post):
    mocked_post.return_value = (403, None, {})
    content, error = http_client_util.SendRequestToServer(
        'http://www.someurl.com',
        FinditHttpClient(403, None),
        post_data={
            'data': 'data'
        })
    self.assertIsNone(content)
    self.assertEqual(403, error['code'], {})
