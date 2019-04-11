# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import mock
import unittest

import crontab

from infra.services.swarm_docker import main_helpers


MAIN_HELPERS = 'infra.services.swarm_docker.main_helpers.'


class TestMainHelpers(unittest.TestCase):
  def setUp(self):
    self.args = argparse.Namespace(
        reboot_schedule=None, canary=False, image_name='swarm_docker:latest',
        registry_project='mock-registry', max_container_uptime=240,
        reboot_grace_period=240)

  @mock.patch(MAIN_HELPERS + 'get_host_uptime', return_value=70)
  @mock.patch(MAIN_HELPERS + 'reboot_host')
  def testRebootOnSchedule(self, reboot_host, _get_host_uptime):
    self.args.reboot_schedule = mock.Mock(spec=crontab.CronTab)
    self.args.reboot_schedule.previous.return_value = -120  # 2 minutes ago
    self.assertTrue(main_helpers.reboot_gracefully(self.args, []))
    reboot_host.assert_called()

  @mock.patch(MAIN_HELPERS + 'get_host_uptime', return_value=70)
  @mock.patch(MAIN_HELPERS + 'reboot_host')
  def testNoRebootOnSchedule(self, reboot_host, _get_host_uptime):
    self.args.reboot_schedule = mock.Mock(spec=crontab.CronTab)
    self.args.reboot_schedule.previous.return_value = -7200  # 2 hours ago
    self.assertFalse(main_helpers.reboot_gracefully(self.args, []))
    reboot_host.assert_not_called()

  @mock.patch(MAIN_HELPERS + 'get_host_uptime', return_value=70)
  @mock.patch(MAIN_HELPERS + 'reboot_host')
  def testRebootOnMaxHostUptime(self, reboot_host, _get_host_uptime):
    self.args.max_host_uptime = 60
    self.assertTrue(main_helpers.reboot_gracefully(self.args, []))
    reboot_host.assert_called()

  @mock.patch(MAIN_HELPERS + 'get_host_uptime', return_value=70)
  @mock.patch(MAIN_HELPERS + 'reboot_host')
  def testNoRebootWithContainers(self, reboot_host, _get_host_uptime):
    self.args.max_host_uptime = 60
    self.assertTrue(main_helpers.reboot_gracefully(self.args, [mock.Mock()]))
    reboot_host.assert_not_called()

  @mock.patch(MAIN_HELPERS + 'get_host_uptime', return_value=310)
  @mock.patch(MAIN_HELPERS + 'reboot_host')
  def testForceRebootAfterGracePeriod(self, reboot_host, _get_host_uptime):
    self.args.max_host_uptime = 60
    self.assertTrue(main_helpers.reboot_gracefully(self.args, [mock.Mock()]))
    reboot_host.assert_called()

  @mock.patch(MAIN_HELPERS + 'get_host_uptime', return_value=50)
  @mock.patch(MAIN_HELPERS + 'reboot_host')
  def testNoRebootBeforeMaxUptime(self, reboot_host, _get_host_uptime):
    self.args.max_host_uptime = 60
    self.assertFalse(main_helpers.reboot_gracefully(self.args, [mock.Mock()]))
    reboot_host.assert_not_called()
