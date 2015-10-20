# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from waterfall.failure_signal import FailureSignal


class FailureSignalTest(unittest.TestCase):
  def testAddFileWithLineNumber(self):
    signal = FailureSignal()
    signal.AddFile('a.cc', 1)
    signal.AddFile('a.cc', 11)
    signal.AddFile('a.cc', 11)
    self.assertEqual({'a.cc': [1, 11]}, signal.files)

  def testAddFileWithoutLineNumber(self):
    signal = FailureSignal()
    signal.AddFile('a.cc', None)
    self.assertEqual({'a.cc': []}, signal.files)

  def testAddKeyWord(self):
    signal = FailureSignal()
    signal.AddKeyword(' ')
    signal.AddKeyword('a')
    signal.AddKeyword('b')
    signal.AddKeyword('a')
    self.assertEqual({'a': 2, 'b': 1}, signal.keywords)

  def testToFromDict(self):
    data = {
        'files': {
            'a.cc': [2],
            'd.cc': []
        },
        'keywords': {
            'k1': 3
        }
    }
    signal = FailureSignal.FromDict(data)
    self.assertEqual(data, signal.ToDict())
