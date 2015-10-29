# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import shutil
import sys
import tempfile
import unittest

import mock

from infra.services.service_manager import root_setup


class RootSetupTest(unittest.TestCase):
  @unittest.skipIf(sys.platform == 'win32', 'windows')
  def setUp(self):
    self.temp_path = tempfile.mkdtemp()

    self.old_upstart_config_filename = root_setup.UPSTART_CONFIG_FILENAME
    self.old_services_directory = root_setup.SERVICES_DIRECTORY
    root_setup.UPSTART_CONFIG_FILENAME = os.path.join(self.temp_path, 'config')
    root_setup.SERVICES_DIRECTORY = os.path.join(self.temp_path, 'services')

    self.mock_getuid = mock.patch('os.getuid').start()
    self.mock_check_call = mock.patch('subprocess.check_call').start()
    self.mock_check_output = mock.patch('subprocess.check_output').start()

    self.mock_getuid.return_value = 0
    self.mock_check_output.return_value = ''

  def tearDown(self):
    mock.patch.stopall()

    root_setup.UPSTART_CONFIG_FILENAME = self.old_upstart_config_filename
    root_setup.SERVICES_DIRECTORY = self.old_services_directory

    shutil.rmtree(self.temp_path)

  def test_non_root(self):
    self.mock_getuid.return_value = 42
    self.assertEquals(1, root_setup.root_setup())

  def test_creates_services_directory(self):
    self.assertFalse(os.path.exists(root_setup.SERVICES_DIRECTORY))
    self.assertEquals(0, root_setup.root_setup())
    self.assertTrue(os.path.exists(root_setup.SERVICES_DIRECTORY))

  def test_services_directory_already_exists(self):
    os.mkdir(root_setup.SERVICES_DIRECTORY)
    self.assertEquals(0, root_setup.root_setup())
    self.assertTrue(os.path.exists(root_setup.SERVICES_DIRECTORY))

  def test_writes_upstart_config(self):
    self.assertFalse(os.path.exists(root_setup.UPSTART_CONFIG_FILENAME))
    self.assertEquals(0, root_setup.root_setup())
    contents = open(root_setup.UPSTART_CONFIG_FILENAME).read()
    self.assertIn('run.py infra.services.service_manager', contents)

  def test_starts_service(self):
    self.assertEquals(0, root_setup.root_setup())
    self.assertEquals(2, self.mock_check_call.call_count)
    self.mock_check_call.assert_called_with(
        ['initctl', 'start', 'service_manager'])

  def test_does_not_restart_service(self):
    self.mock_check_output.return_value = 'service_manager start/running'
    self.assertEquals(0, root_setup.root_setup())
    self.assertEquals(1, self.mock_check_call.call_count)

  def test_write_service(self):
    self.assertEquals(0, root_setup.root_setup())
    root_setup.write_service('foo', 'bar', 'baz', [1, 2])

    path = os.path.join(root_setup.SERVICES_DIRECTORY, 'foo.json')
    contents = open(path).read()
    self.assertEquals({
        'name': 'foo',
        'root_directory': 'bar',
        'tool': 'baz',
        'args': [1, 2],
    }, json.loads(contents))
