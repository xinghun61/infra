# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

import infra.path_hacks.slave

class SlavePathTest(unittest.TestCase):
  def test_check_valid_slave_path(self):
    # This supposes that all proper sibling directories have been checked out.
    slave_path = infra.path_hacks.slave._build_scripts_slave
    self.assertTrue(os.path.isdir(slave_path),
                    msg='Path %s cannot be found, make sure you have checked'
                        ' out this repository with gclient.' % slave_path)
