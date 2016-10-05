# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from findit import findit


class FindItAPITestCase(unittest.TestCase):
  def setUp(self):
    super(FindItAPITestCase, self).setUp()
    self.maxDiff = None
    self.client = mock.Mock()
    self.patchers = [
        mock.patch('endpoints.endpoints.build_client',
                   lambda *_, **__: self.client),
        mock.patch('endpoints.endpoints.retry_request', mock.Mock()),
    ]
    for patcher in self.patchers:
      patcher.start()

  def tearDown(self):
    super(FindItAPITestCase, self).tearDown()
    for patcher in self.patchers:
      patcher.stop()

  def test_creates_flake_request_correctly(self):
    flake = mock.Mock(is_step=True, issue_id=123456)
    flake.name = 'foo'

    pb_run = mock.Mock(master='tryserver.bar', builder='baz')
    failure_run1 = mock.Mock(buildnumber=10)
    failure_run1.parent.get.return_value = pb_run
    failure_run2 = mock.Mock(buildnumber=20)
    failure_run2.parent.get.return_value = pb_run
    flaky_run1 = mock.Mock(flakes=[mock.Mock()])
    flaky_run1.failure_run.get.return_value = failure_run1
    flaky_run1.flakes[0].name = 'step1'
    flaky_run2 = mock.Mock(flakes=[mock.Mock(), mock.Mock()])
    flaky_run2.failure_run.get.return_value = failure_run2
    flaky_run2.flakes[0].name = 'step2'
    flaky_run2.flakes[1].name = 'step3'

    api = findit.FindItAPI()
    api.flake(flake, [flaky_run1, flaky_run2])
    self.assertEquals(self.client.flake.call_count, 1)
    self.assertDictEqual(self.client.flake.call_args[1]['body'], {
      'name': 'foo',
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
        {
          'master_name': 'tryserver.bar',
          'builder_name': 'baz',
          'build_number': 20,
          'step_name': 'step3'
        }
      ]
    })
