# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from waterfall.extractor import Extractor
from waterfall.failure_signal import FailureSignal


class ExtractorTest(unittest.TestCase):
  def testExtractFiles(self):
    cases = {
        'a/b/c.h:1 at d/e/f.cpp(2)': {
            'a/b/c.h': [1],
            'd/e/f.cpp': [2]
        },
        'blabla telemetry/decorators.py:55': {
            'telemetry/decorators.py': [55]
        },
        'File "telemetry/core/web_contents.py", line 78, in pythonMethod': {
            'telemetry/core/web_contents.py': [78]
        },
    }

    extractor = Extractor()
    for case in cases:
      signal = FailureSignal()
      extractor.ExtractFiles(case, signal)
      self.assertEqual(cases[case], signal.ToJson()['files'])
