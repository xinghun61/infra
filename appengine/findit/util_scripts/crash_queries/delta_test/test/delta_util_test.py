# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from crash_queries.delta_test import delta_util


class DeltaUtilTest(unittest.TestCase):

  def testEncodeStrForCSV(self):
    string = '{\n"a": 1,\n"b": 2}'
    self.assertEqual('{\n\'a\': 1,\n\'b\': 2}',
                     delta_util._EncodeStrForCSV(string))

    string = 'a cat says "one", "two"\\'
    self.assertEqual('a cat says \'one\', \'two\'\\',
                     delta_util._EncodeStrForCSV(string))
