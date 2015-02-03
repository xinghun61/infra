# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

import infra.path_hacks.common

class CommonPathTest(unittest.TestCase):
  def test_check_valid_common_path(self):
    # This supposes that all proper sibling directories have been checked out.
    common_path = infra.path_hacks.common._build_scripts_common
    self.assertTrue(os.path.isdir(common_path),
                    msg='Path %s cannot be found, make sure you have checked'
                        ' out this repository with gclient.' % common_path)
