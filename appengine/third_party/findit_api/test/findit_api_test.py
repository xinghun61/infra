# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

from findit_api import findit_api
from testing_support import auto_stub

class FindItAPITestCase(auto_stub.TestCase):
  def setUp(self):
    super(FindItAPITestCase, self).setUp()
    self.maxDiff = None
    self.client = mock.Mock()
    self.build_client = mock.Mock(return_value=self.client)
    self.patchers = [
        mock.patch(
            'endpoints_client.endpoints.build_client', self.build_client),
        mock.patch('endpoints_client.endpoints.retry_request', mock.Mock()),
    ]
    for patcher in self.patchers:
      patcher.start()

  def tearDown(self):
    for patcher in self.patchers:
      patcher.stop()
    super(FindItAPITestCase, self).tearDown()

  def test_creates_flake_request_correctly(self):
    api = findit_api.FindItAPI()
    occurrences = [
      {
        'master_name': 'tryserver.bar',
        'builder_name': 'baz',
        'build_number': 10,
        'step_name': 'step1'
      },
      {
        'master_name': 'tryserver.bar',
        'builder_name': 'baz',
        'build_number': 20,
        'step_name': 'step2'
      },
    ]
    api.flake('testX', True, 123456, occurrences)
    self.assertEquals(self.client.flake.call_count, 1)
    self.assertDictEqual(self.client.flake.call_args[1]['body'], {
      'name': 'testX',
      'is_step': True,
      'bug_id': 123456,
      'build_steps': [
        {
          'master_name': 'tryserver.bar',
          'builder_name': 'baz',
          'build_number': 10,
          'step_name': 'step1'
        },
        {
          'master_name': 'tryserver.bar',
          'builder_name': 'baz',
          'build_number': 20,
          'step_name': 'step2'
        },
      ]
    })

  def test_uses_staging_instance(self):
    findit_api.FindItAPI(use_staging=True)
    self.assertEquals(self.build_client.call_count, 1)
    self.assertEquals(self.build_client.call_args[0][0], 'findit')
    self.assertEquals(self.build_client.call_args[0][1], 'v1')
    self.assertEquals(
        self.build_client.call_args[0][2], 'https://findit-for-me-staging.'
        'appspot.com/_ah/api/discovery/v1/apis/{api}/{apiVersion}/rest')

  def test_uses_prod_instance_by_default(self):
    findit_api.FindItAPI()
    self.assertEquals(self.build_client.call_count, 1)
    self.assertEquals(self.build_client.call_args[0][0], 'findit')
    self.assertEquals(self.build_client.call_args[0][1], 'v1')
    self.assertEquals(
        self.build_client.call_args[0][2], 'https://findit-for-me.appspot.com/'
        '_ah/api/discovery/v1/apis/{api}/{apiVersion}/rest')
