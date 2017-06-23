# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from libs.gitiles.diff import ChangeType
from libs.gitiles.diff import IsKnownChangeType


class DiffTest(unittest.TestCase):

  def testKnownChangeTypes(self):
    for change_type in [
        ChangeType.ADD, ChangeType.DELETE, ChangeType.MODIFY, ChangeType.COPY,
        ChangeType.RENAME
    ]:
      self.assertTrue(IsKnownChangeType(change_type))

  def testUnknownChangeType(self):
    self.assertFalse(IsKnownChangeType('unknown change type'))
