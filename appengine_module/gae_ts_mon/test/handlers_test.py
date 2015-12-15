# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import gae_ts_mon
import mock
import webapp2

from infra_libs.ts_mon import config
from infra_libs.ts_mon import handlers
from infra_libs.ts_mon.common import interface
from infra_libs.ts_mon.common.test import stubs
from testing_utils import testing


class HandlersTest(testing.AppengineTestCase):
  def setUp(self):
    super(HandlersTest, self).setUp()

    self.mock_state = stubs.MockState()
    mock.patch('infra_libs.ts_mon.common.interface.state',
        new=self.mock_state).start()

    mock.patch('infra_libs.ts_mon.config.initialize', autospec=True).start()
    mock.patch('infra_libs.ts_mon.common.interface.flush',
               autospec=True).start()

  def tearDown(self):
    super(HandlersTest, self).tearDown()

    mock.patch.stopall()

  def test_unauthorized(self):
    request = webapp2.Request.blank('/internal/cron/ts_mon/send')
    response = request.get_response(handlers.app)

    self.assertEqual(response.status_int, 403)
    self.assertFalse(interface.flush.called)

  def test_initialized(self):
    request = webapp2.Request.blank('/internal/cron/ts_mon/send')
    request.headers['X-Appengine-Cron'] = 'true'
    self.mock_state.global_monitor = mock.Mock()
    response = request.get_response(handlers.app)

    self.assertEqual(response.status_int, 200)
    self.assertFalse(config.initialize.called)
    interface.flush.assert_called_once_with()

