# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing


class StacktraceTestSuite(testing.AppengineTestCase):  #pragma: no cover.

  def _VerifyTwoStackFramesEqual(self, frame1, frame2):
    self.assertEqual(str(frame1), str(frame2))
    self.assertEqual(frame1.dep_path, frame2.dep_path)
    self.assertEqual(frame1.component, frame2.component)

  def _VerifyTwoCallStacksEqual(self, stack1, stack2):
    self.assertEqual(len(stack1), len(stack2))
    self.assertEqual(stack1.priority, stack2.priority)
    self.assertEqual(stack1.format_type, stack2.format_type)
    map(self._VerifyTwoStackFramesEqual, stack1, stack2)

  def _VerifyTwoStacktracesEqual(self, stacktrace1, stacktrace2):
    self.assertEqual(len(stacktrace1), len(stacktrace2))
    map(self._VerifyTwoCallStacksEqual, stacktrace1, stacktrace2)
