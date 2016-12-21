# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import StringIO
import unittest

import mock

from infra.services.service_manager import cloudtail_factory


class CloudtailFactoryTest(unittest.TestCase):
  def setUp(self):
    self.mock_popen = mock.patch('subprocess.Popen', autospec=True).start()

  def tearDown(self):
    mock.patch.stopall()

  def test_start(self):
    fh = mock.Mock()

    f = cloudtail_factory.CloudtailFactory('/foo', None)
    f.start('log', fh)

    self.assertEqual(1, self.mock_popen.call_count)
    self.assertEqual(
        ['/foo', 'pipe', '--log-id', 'log', '--local-log-level', 'info'],
        self.mock_popen.call_args[0][0])

    kwargs = self.mock_popen.call_args[1]
    self.assertEqual(fh, kwargs['stdin'])
    self.assertIn('stdout', kwargs)
    self.assertIn('stderr', kwargs)

  def test_start_with_credentials(self):
    f = cloudtail_factory.CloudtailFactory('/foo', '/bar')
    f.start('log', mock.Mock())

    self.assertEqual(1, self.mock_popen.call_count)
    self.assertEqual(
        ['/foo', 'pipe', '--log-id', 'log', '--local-log-level', 'info',
         '--ts-mon-credentials', '/bar'],
        self.mock_popen.call_args[0][0])

  def test_start_with_kwargs(self):
    f = cloudtail_factory.CloudtailFactory('/foo', None)
    f.start('log', mock.Mock(), cwd='bar')

    self.assertEqual(1, self.mock_popen.call_count)
    kwargs = self.mock_popen.call_args[1]
    self.assertEqual('bar', kwargs['cwd'])


class DummyCloudtailFactoryTest(unittest.TestCase):
  def test_start(self):
    f = cloudtail_factory.DummyCloudtailFactory()

    with self.assertRaises(OSError):
      f.start('foo', mock.Mock())
