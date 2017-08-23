# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from analysis import component
from analysis import stacktrace


class ComponentTest(unittest.TestCase):
  """Tests ``Component`` class."""

  def testMatchesStackFrameWhenFrameHasNoPathInformation(self):
    """``MatchesStackFrame`` shouldn't crash when frame has no path info."""
    component_object = component.Component('name', ['dirs/'])
    frame = stacktrace.ProfilerStackFrame(0, 5, 0.21, False, dep_path=None,
                                          file_path=None, raw_file_path=None)
    self.assertFalse(component_object.MatchesStackFrame(frame))
