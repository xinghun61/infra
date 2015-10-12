# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ctypes
import os
import sys
import unittest

import mock

from infra_libs import temporary_directory
from infra.services.mastermon import monitor
from infra.services.mastermon import pollers
import infra_libs


class MasterMonitorTest(unittest.TestCase):
  def test_poll(self):
    mock_poller_class = mock.create_autospec(pollers.Poller, spec_set=True)
    mock_poller = mock_poller_class.return_value

    class MasterMonitor(monitor.MasterMonitor):
      POLLER_CLASSES = [mock_poller_class]

    m = MasterMonitor('http://example.com')

    mock_poller.poll.return_value = True
    m.poll()
    self.assertTrue(m.up.get())

    mock_poller.poll.return_value = False
    m.poll()
    self.assertFalse(m.up.get())

  def test_poll_with_name(self):
    mock_poller_class = mock.create_autospec(pollers.Poller, spec_set=True)
    mock_poller = mock_poller_class.return_value

    class MasterMonitor(monitor.MasterMonitor):
      POLLER_CLASSES = [mock_poller_class]

    m = MasterMonitor('http://example.com', name='foobar')

    mock_poller.poll.return_value = True
    m.poll()
    self.assertTrue(m.up.get({'master': 'foobar'}))

    mock_poller.poll.return_value = False
    m.poll()
    self.assertFalse(m.up.get({'master': 'foobar'}))

  def test_ts_mon_file_deletion(self):
    class MasterMonitor(monitor.MasterMonitor):
      POLLER_CLASSES = []

    with temporary_directory(prefix='monitor-test-') as tempdir:
      ts_mon_filename = os.path.join(tempdir, 'ts_mon.json')
      with open(ts_mon_filename, 'w') as f:
        f.write(' ')
      self.assertTrue(os.path.isfile(ts_mon_filename))
      MasterMonitor('http://example.com',
                    name='foobar',
                    results_file=ts_mon_filename)
      self.assertFalse(os.path.isfile(ts_mon_filename))

  def test_ts_mon_file_polling_file_missing(self):
    # Test that asking to poll a missing file works.
    # Mostly a smoke test.
    class MasterMonitor(monitor.MasterMonitor):
      POLLER_CLASSES = []

    with temporary_directory(prefix='monitor-test-') as tempdir:
      ts_mon_filename = os.path.join(tempdir, 'ts_mon.json')
      self.assertFalse(os.path.isfile(ts_mon_filename))
      MasterMonitor('http://example.com',
                    name='foobar',
                    results_file=ts_mon_filename)
      self.assertFalse(os.path.isfile(ts_mon_filename))

  @mock.patch('subprocess.Popen')
  def test_starts_cloudtail(self, mock_popen):
    m = monitor.MasterMonitor('http://example.com',
                              name='foobar',
                              log_file='/foo/bar',
                              cloudtail_path='/cloudtail')

    self.assertEqual(1, mock_popen.call_count)
    args = mock_popen.call_args[0][0]
    self.assertEqual('/cloudtail', args[0])
    self.assertIn('/foo/bar', args)
    self.assertIn('foobar', args)
    self.assertEqual(mock_popen.return_value, m._cloudtail)

  @mock.patch('subprocess.Popen')
  def test_starts_cloudtail_failure(self, mock_popen):
    mock_popen.side_effect = OSError

    m = monitor.MasterMonitor('http://example.com',
                              name='foobar',
                              log_file='/foo/bar',
                              cloudtail_path='/cloudtail')

    self.assertEqual(1, mock_popen.call_count)
    self.assertIsNone(m._cloudtail)


class MastermapTest(unittest.TestCase):
  def test_create_from_mastermap(self):
    specs = [
      {'port': 1234, 'dirname': 'master.foo.bar'},
      {'port': 5678, 'dirname': 'master.baz'},
    ]
    monitors = monitor._create_from_mastermap('/doesnotexist', specs, None)

    self.assertEqual(len(specs), len(monitors))
    for mon, spec in zip(monitors, specs):
      self.assertEqual(2, len(mon._pollers))
      self.assertTrue(mon._pollers[0]._url.startswith(
          'http://localhost:%s/' % spec['port']))
      self.assertEqual({'master': spec['dirname']},
                       mon._pollers[0].fields())
      self.assertEqual(mon._pollers[1]._url,
                       monitor.RESULTS_FILE % spec['dirname'])

  @mock.patch('subprocess.Popen')
  def test_tails_log(self, mock_popen):
    specs = [
      {'port': 1234, 'dirname': 'master.foo'},
    ]

    with infra_libs.temporary_directory() as temp_dir:
      # Create a master directory with an empty twistd.log
      build_dir = os.path.join(temp_dir, 'build')
      master_dir = os.path.join(temp_dir, 'build/masters/master.foo')
      log_path = os.path.join(master_dir, 'twistd.log')
      os.makedirs(master_dir)
      with open(log_path, 'w'):
        pass

      monitors = monitor._create_from_mastermap(
          build_dir, specs, '/path/to/cloudtail')

    self.assertEqual(1, len(monitors))
    self.assertEqual(1, mock_popen.call_count)
    self.assertEqual(mock_popen.return_value, monitors[0]._cloudtail)

    args = mock_popen.call_args[0][0]
    self.assertEqual('/path/to/cloudtail', args[0])
    self.assertIn('master.foo', args)
    self.assertIn(log_path, args)

  @mock.patch('subprocess.Popen')
  def test_tails_log_internal(self, mock_popen):
    specs = [
      {'port': 1234, 'dirname': 'master.foo'},
    ]

    with infra_libs.temporary_directory() as temp_dir:
      # Create a master directory with an empty twistd.log
      build_dir = os.path.join(temp_dir, 'build')
      master_dir = os.path.join(temp_dir, 'build_internal/masters/master.foo')
      log_path = os.path.join(master_dir, 'twistd.log')
      os.makedirs(master_dir)
      with open(log_path, 'w'):
        pass

      monitors = monitor._create_from_mastermap(
          build_dir, specs, '/path/to/cloudtail')

    self.assertEqual(1, len(monitors))
    self.assertEqual(1, mock_popen.call_count)
    self.assertEqual(mock_popen.return_value, monitors[0]._cloudtail)

    args = mock_popen.call_args[0][0]
    self.assertEqual('/path/to/cloudtail', args[0])
    self.assertIn('master.foo', args)
    self.assertIn(log_path, args)


class SetDeathSigTest(unittest.TestCase):
  def _get_deathsig(self):  # pragma: no cover
    ret = ctypes.c_int()
    ctypes.cdll.LoadLibrary('libc.so.6').prctl(2, ctypes.byref(ret), 0, 0, 0)
    return ret.value

  @unittest.skipUnless(sys.platform == 'linux2', 'Only works on Linux')
  def test_set_deathsig(self):  # pragma: no cover
    monitor.set_deathsig(42)
    self.assertEqual(42, self._get_deathsig())

    monitor.set_deathsig(0)
    self.assertEqual(0, self._get_deathsig())

  @unittest.skipIf(sys.platform == 'linux2', 'Only works on Linux')
  def test_set_deathsig_asserts(self):  # pragma: no cover
    with self.assertRaises(AssertionError):
      monitor.set_deathsig(42)
