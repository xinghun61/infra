# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import zlib

from components import net
from testing_utils import testing

from test.test_util import future

from swarming import isolate


class IsolateTest(testing.AppengineTestCase):
  loc = isolate.Location('swarming.example.com', 'default-gzip', 'deadbeef')

  def setUp(self):
    super(IsolateTest, self).setUp()
    self.patch('components.net.json_request_async', autospec=True)
    self.patch('components.net.request_async', autospec=True)

  def test_fetch_content(self):
    expected = 'foo'
    net.json_request_async.return_value = future({
      'content': base64.b64encode(zlib.compress(expected)),
    })

    actual = isolate.fetch_async(self.loc).get_result()
    self.assertEqual(expected, actual)
    net.json_request_async.assert_called_with(
        'https://swarming.example.com/_ah/api/isolateservice/v1/retrieve',
        method='POST',
        payload={
          'digest': self.loc.digest,
          'namespace': {'namespace': self.loc.namespace},
        },
        scopes=net.EMAIL_SCOPE,
    )

  def test_fetch_net_error(self):
    net.json_request_async.side_effect = net.AuthError('HTTP 403', 403, None)
    with self.assertRaises(isolate.Error):
      isolate.fetch_async(self.loc).get_result()

  def test_fetch_content_not_base64(self):
    net.json_request_async.return_value = future({
      'content': 'sdfsfsd',
    })
    with self.assertRaises(isolate.Error):
      isolate.fetch_async(self.loc).get_result()

  def test_fetch_content_cannot_decompress(self):
    net.json_request_async.return_value = future({
      'content': base64.b64encode('~'),
    })
    with self.assertRaises(isolate.Error):
      isolate.fetch_async(self.loc).get_result()

  def test_fetch_via_url(self):
    expected = 'foo'
    net.json_request_async.return_value = future({
      'url': 'https://example.com/file?a=b',
    })
    net.request_async.return_value = future(zlib.compress(expected))

    actual = isolate.fetch_async(self.loc).get_result()
    self.assertEqual(expected, actual)
    net.request_async.assert_called_with(
        'https://example.com/file',
        params=[('a', 'b')],
    )

  def test_fetch_via_url_error(self):
    net.json_request_async.return_value = future({
      'url': 'https://example.com/file',
    })
    net.request_async.side_effect = net.Error('error', 500, None)

    with self.assertRaises(isolate.Error):
      isolate.fetch_async(self.loc).get_result()

  def test_fetch_no_content_or_url(self):
    net.json_request_async.return_value = future({
      'something_else': 'yeah',
    })
    with self.assertRaises(isolate.Error):
      isolate.fetch_async(self.loc).get_result()
