# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from common import diff
from common.diff import ChangeType

class DiffTest(unittest.TestCase):
  def testKnownChangeTypes(self):
    for change_type in [ChangeType.ADD, ChangeType.DELETE, ChangeType.MODIFY,
                        ChangeType.COPY, ChangeType.RENAME]:
      self.assertTrue(diff.IsKnownChangeType(change_type))

  def testUnknownChangeType(self):
    self.assertFalse(diff.IsKnownChangeType('unknown change type'))
