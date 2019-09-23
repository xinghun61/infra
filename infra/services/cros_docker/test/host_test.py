# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from infra.services.cros_docker import host


class HostTests(unittest.TestCase):
  def test_read_device_list(self):
    device_file = '["somedevice1", "somedevice2"]'
    with mock.patch('__builtin__.open', mock.mock_open(read_data=device_file)):
      devices = host.read_device_list('some_device_path')

    self.assertEqual(devices, ['somedevice1', 'somedevice2'])

  @mock.patch('json.load')
  def test_read_device_wrong_format(self, mock_json):
    mock_json.return_value = 'this is not a list'
    with mock.patch('__builtin__.open', mock.mock_open(read_data='')):
      self.assertRaises(TypeError, host.read_device_list, 'some_device_path')

  @mock.patch('os.path.exists')
  def test_should_write(self, mock_exists):
    mock_exists.side_effect = [True, True]
    with mock.patch('__builtin__.open',
                    mock.mock_open(read_data=host.SSH_CONFIG_FILE_CONTENTS)):
      self.assertFalse(host.should_write_ssh_config())

  @mock.patch('os.path.exists')
  def test_should_write_no_file(self, mock_exists):
    mock_exists.side_effect = [True, False]
    self.assertTrue(host.should_write_ssh_config())

  @mock.patch('os.chown')
  @mock.patch('pwd.getpwnam')
  @mock.patch('os.mkdir')
  @mock.patch('os.path.exists')
  def test_should_write_no_dir(self, mock_exists, mock_mkdir, mock_pwn,
                               mock_chown):
    mock_exists.side_effect = [False, False]
    self.assertTrue(host.should_write_ssh_config())
    mock_pwn.assert_called_once()
    mock_mkdir.assert_called_once()
    mock_chown.assert_called_once()

  @mock.patch('os.path.exists')
  def test_should_write_wrong_contents(self, mock_exists):
    mock_exists.return_value = True
    with mock.patch('__builtin__.open',
                    mock.mock_open(read_data='this aint right')):
      self.assertTrue(host.should_write_ssh_config())

  def test_write_config(self):
    with mock.patch('__builtin__.open', mock.mock_open()):
      host.write_ssh_config()
