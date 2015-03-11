# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=F0401

import unittest

from infra.tools.bot_setup.version import version


ENABLED_SLAVES = [
  'slave2-c7',
  'slave12-c7',
  'slave100-c4',
  'slave250-c4',
  'slave260-c4',
  'swarm1-c4',
  'swarm11-c4',
  'winslave1-c4',
  'swarm-win1-c4',
]

DISABLED_SLAVES = [
  'test_disabled_slave',
]


class TestVersions(unittest.TestCase):
  @staticmethod
  def test_expected_active_versions():
    return [
      'Slave %s is on version %s'
      % (slave_name, version.get_version(slave_name, None))
      for slave_name in sorted(ENABLED_SLAVES)
    ]

  def test_expected_disabled_versions(self):
    for slave_name in sorted(DISABLED_SLAVES):
      self.assertRaises(
          version.BuilderDisabled, version.get_version, slave_name, None)
