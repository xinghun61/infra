# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import mock

from testing_utils import testing

from gae_libs.http import http_client_appengine
from common.swarmbucket import swarmbucket

_MOCK_TASK_DEF_RESPONSE = json.dumps({
    'task_definition':
        json.dumps({
            'properties': {
                'dimensions': [{
                    'value': 'x86-64',
                    'key': 'cpu'
                }, {
                    'value': 'Ubuntu-14.04',
                    'key': 'os'
                }, {
                    'value': 'Chrome.LUCI',
                    'key': 'pool'
                }]
            }
        }),
})


class SwarmbucketTest(testing.AppengineTestCase):

  def setUp(self):
    super(SwarmbucketTest, self).setUp()
    self.maxDiff = None

  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testGetDimensionsSuccessful(self, mock_fetch):
    mock_fetch.return_value = collections.namedtuple(
        'Result', ['content', 'status_code', 'headers'])(
            status_code=200, content=_MOCK_TASK_DEF_RESPONSE, headers={})
    dimensions = swarmbucket.GetDimensionsForBuilder('Linux x64')
    self.assertEqual(['cpu:x86-64', 'os:Ubuntu-14.04', 'pool:Chrome.LUCI'],
                     dimensions)

  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testGetDimensionsFailed(self, mock_fetch):
    mock_fetch.return_value = collections.namedtuple(
        'Result', ['content', 'status_code', 'headers'])(
            status_code=501, content=_MOCK_TASK_DEF_RESPONSE, headers={})
    dimensions = swarmbucket.GetDimensionsForBuilder('Linux x64')
    self.assertFalse(dimensions)
