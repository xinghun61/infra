# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest


class UpdateTestsetTest(unittest.TestCase):

  def testScriptCanLoad(self):
    """Basic sanity check to ensure the update-testset.py script can load."""
    __import__('scripts.testset.update-testset')

  # TODO(crbug/662540): Add more tests.
