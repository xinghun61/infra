# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit test for generate_features."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from features import generate_dataset


class GenerateFeaturesTest(unittest.TestCase):

  def testCleanText(self):
    sampleText = """Here's some sample text...$*IT should l00k much\n\n\t,
                    _much_MUCH better \"cleaned\"!"""
    self.assertEqual(generate_dataset.CleanText(sampleText),
                     ("heres some sample text it should l00k much much much "
                      "better cleaned"))
    emptyText = ""
    self.assertEqual(generate_dataset.CleanText(emptyText), "")
