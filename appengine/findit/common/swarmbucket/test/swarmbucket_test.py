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
            'task_slices': [{
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
            }]
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
    dimensions = swarmbucket.GetDimensionsForBuilder(
        'luci.chromium.ci', 'Linux x64', dimensions_whitelist=None)
    self.assertEqual(['cpu:x86-64', 'os:Ubuntu-14.04', 'pool:Chrome.LUCI'],
                     dimensions)
    dimensions = swarmbucket.GetDimensionsForBuilder('luci.chromium.ci',
                                                     'Linux x64')
    self.assertEqual(['cpu:x86-64', 'os:Ubuntu-14.04'], dimensions)
    _args, kwargs = mock_fetch.call_args
    self.assertEqual(http_client_appengine.urlfetch.POST, kwargs.get('method'))

  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testGetDimensionsFailed(self, mock_fetch):
    mock_fetch.return_value = collections.namedtuple(
        'Result', ['content', 'status_code', 'headers'])(
            status_code=501, content=_MOCK_TASK_DEF_RESPONSE, headers={})
    dimensions = swarmbucket.GetDimensionsForBuilder('luci.chromium.ci',
                                                     'Linux x64')
    self.assertFalse(dimensions)

  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testGetBuilders(self, mock_fetch):
    mock_builders_response = json.dumps({
        'buckets': [{
            'builders': [
                {
                    'name': 'findit_variable',
                },
                {
                    'name': 'linux_chromium_bot_db_exporter',
                },
            ],
            'name':
                'luci.chromium.findit'
        },]
    })
    mock_fetch.return_value = collections.namedtuple(
        'Result', ['content', 'status_code', 'headers'])(
            status_code=200, content=mock_builders_response, headers={})
    builders = swarmbucket.GetBuilders('luci.chromium.findit')
    self.assertIn('findit_variable', builders)
    _args, kwargs = mock_fetch.call_args
    self.assertEqual(http_client_appengine.urlfetch.GET, kwargs.get('method'))

  @mock.patch.object(http_client_appengine.urlfetch, 'fetch')
  def testGetMasters(self, mock_fetch):
    mock_builders_response = json.dumps({
        'buckets': [{
            'builders': [
                {
                    'name':
                        'Linux Tests',
                    'properties_json':
                        json.dumps({
                            'mastername': 'chromium.linux'
                        })
                },
                {
                    'name':
                        'Mac Tests',
                    'properties_json':
                        json.dumps({
                            'mastername': 'chromium.mac'
                        })
                },
            ],
            'name':
                'luci.chromium.ci'
        },]
    })
    mock_fetch.return_value = collections.namedtuple(
        'Result', ['content', 'status_code', 'headers'])(
            status_code=200, content=mock_builders_response, headers={})
    masters = swarmbucket.GetMasters('luci.chromium.ci')
    self.assertItemsEqual(masters, ['chromium.mac', 'chromium.linux'])
    _args, kwargs = mock_fetch.call_args
    self.assertEqual(http_client_appengine.urlfetch.GET, kwargs.get('method'))
