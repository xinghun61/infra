# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for ../luci_check.py"""

import argparse
import unittest
import mock

from infra.tools.luci_check import luci_check
from infra.tools.luci_check import project_pb2 as proj


class LuciCheckTest(unittest.TestCase):
  def setUp(self):
    console_def = proj.Project()
    console1 = console_def.consoles.add()
    console1.id = "first"
    builder1 = console1.builders.add()
    builder1.name.append('a/b/foo')
    self.lc = luci_check.Checker('https://example.com')
    self.lc.get_console_def = lambda: console_def
    self.lc.get_master = mock.Mock()

  def test_not_found(self):
    self.lc.get_master.return_value = False
    self.assertEqual(self.lc.check(), 0)

  def test_ok(self):
    self.lc.get_master.return_value = {'builders': {'foo': {}}}
    self.assertEqual(self.lc.check(), 0)

  def test_diff(self):
    self.lc.get_master.return_value = {'builders': {'bar': {}}}
    self.assertEqual(self.lc.check(), 1)
