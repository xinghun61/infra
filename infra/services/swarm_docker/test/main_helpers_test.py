# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import mock
import random
import string
import unittest

from infra.services.swarm_docker import main_helpers


MAIN_HELPERS = 'infra.services.swarm_docker.main_helpers.'


class TestMainHelpers(unittest.TestCase):
  def setUp(self):
    self.args = argparse.Namespace(
        reboot_schedule=None, canary=False, image_name='swarm_docker:latest',
        registry_project='mock-registry', max_container_uptime=240,
        reboot_grace_period=240)

  def testGetUptime(self):
    uptime = '1440.75 103734.55'
    with mock.patch("__builtin__.open", mock.mock_open(read_data=uptime)) as _:
      self.assertEqual(main_helpers.get_host_uptime(), 24.0125)

  @mock.patch(MAIN_HELPERS + 'fuzz_max_uptime', return_value=60)
  @mock.patch(MAIN_HELPERS + 'get_host_uptime', return_value=70)
  @mock.patch(MAIN_HELPERS + 'reboot_host')
  def testRebootOnMaxHostUptime(self, reboot_host, _, __):
    self.args.max_host_uptime = 60
    self.assertTrue(main_helpers.reboot_gracefully(self.args, []))
    reboot_host.assert_called()

  @mock.patch(MAIN_HELPERS + 'fuzz_max_uptime', return_value=60)
  @mock.patch(MAIN_HELPERS + 'get_host_uptime', return_value=70)
  @mock.patch(MAIN_HELPERS + 'reboot_host')
  def testNoRebootWithContainers(self, reboot_host, _, __):
    self.args.max_host_uptime = 60
    self.assertTrue(main_helpers.reboot_gracefully(self.args, [mock.Mock()]))
    reboot_host.assert_not_called()

  @mock.patch(MAIN_HELPERS + 'fuzz_max_uptime', return_value=60)
  @mock.patch(MAIN_HELPERS + 'get_host_uptime', return_value=310)
  @mock.patch(MAIN_HELPERS + 'reboot_host')
  def testForceRebootAfterGracePeriod(self, reboot_host, _, __):
    self.args.max_host_uptime = 60
    self.assertTrue(main_helpers.reboot_gracefully(self.args, [mock.Mock()]))
    reboot_host.assert_called()

  @mock.patch(MAIN_HELPERS + 'fuzz_max_uptime', return_value=60)
  @mock.patch(MAIN_HELPERS + 'get_host_uptime', return_value=50)
  @mock.patch(MAIN_HELPERS + 'reboot_host')
  def testNoRebootBeforeMaxUptime(self, reboot_host, _, __):
    self.args.max_host_uptime = 60
    self.assertFalse(main_helpers.reboot_gracefully(self.args, [mock.Mock()]))
    reboot_host.assert_not_called()

  @mock.patch('socket.getfqdn')
  def test_deterministic_fuzz(self, mock_gethostname):
    hostname = 'some_hostname'
    fuzz_amount = 113  # md5sum'ed the hostname module 240 (20% of 1200)
    mock_gethostname.return_value = hostname

    fuzzed_max_uptime = main_helpers.fuzz_max_uptime(1200)
    self.assertEqual(fuzzed_max_uptime - 1200, fuzz_amount)

  @mock.patch('socket.getfqdn')
  def test_fuzz_range(self, mock_gethostname):
    # Test a bunch of random hostnames.
    for n in xrange(1, 101):
      hostname = ''.join([random.choice(string.lowercase) for _ in xrange(n)])
      mock_gethostname.return_value = hostname
      fuzzed_amount = main_helpers.fuzz_max_uptime(1200) - 1200
      self.assertGreaterEqual(fuzzed_amount, 0)
      self.assertLess(fuzzed_amount, 240)
