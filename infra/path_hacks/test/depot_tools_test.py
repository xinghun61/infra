# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

import infra.path_hacks.depot_tools

class DepotToolsPathTest(unittest.TestCase):
  def test_check_valid_depot_tools_path(self):
    # This supposes that all proper sibling directories have been checked out.
    depot_tools_path = infra.path_hacks.depot_tools._depot_tools
    self.assertTrue(os.path.isdir(depot_tools_path),
                    msg='Path %s cannot be found, make sure you have checked'
                        ' out this repository with gclient.' % depot_tools_path)
