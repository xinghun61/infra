# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

import infra.path_hacks.master

class MasterPathTest(unittest.TestCase):
  def test_check_valid_master_path(self):
    # This supposes that all proper sibling directories have been checked out.
    master_path = infra.path_hacks.master._build_scripts_master
    self.assertTrue(os.path.isdir(master_path),
                    msg='Path %s cannot be found, make sure you have checked'
                        ' out this repository with gclient.' % master_path)
