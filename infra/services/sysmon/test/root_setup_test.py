# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock

from infra.services.sysmon import root_setup


class RootSetupTest(unittest.TestCase):
  def setUp(self):
    self.mock_write_service = mock.patch(
        'infra.services.service_manager.root_setup.write_service').start()

  def tearDown(self):
    mock.patch.stopall()

  def test_writes_service(self):
    self.assertEquals(0, root_setup.root_setup())
    self.mock_write_service.assert_called_once_with(
        name='sysmon',
        root_directory='/opt/infra-python',
        tool='infra.services.sysmon',
        args=['--interval', '60'])
