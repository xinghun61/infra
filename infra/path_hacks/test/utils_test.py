# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

import infra.path_hacks

class FullInfraPathTest(unittest.TestCase):
  def test_check_valid_full_infra_path(self):
    self.assertTrue(os.path.isdir(infra.path_hacks.full_infra_path))
