# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from crash.test.crash_testcase import CrashTestCase


class StacktraceTestSuite(CrashTestCase):  #pragma: no cover.

  def _VerifyTwoStackFramesEqual(self, frame1, frame2):
    self.assertIsNotNone(frame1, "the first frame is unexpectedly missing")
    self.assertIsNotNone(frame2, "the second frame is unexpectedly missing")
    self.assertEqual(str(frame1), str(frame2))
    self.assertEqual(frame1.dep_path, frame2.dep_path)

  def _VerifyTwoCallStacksEqual(self, stack1, stack2):
    self.assertIsNotNone(stack1, "the first stack is unexpectedly missing")
    self.assertIsNotNone(stack2, "the second stack is unexpectedly missing")
    self.assertEqual(len(stack1.frames), len(stack2.frames))
    self.assertEqual(stack1.priority, stack2.priority)
    self.assertEqual(stack1.format_type, stack2.format_type)
    self.assertEqual(stack1.language_type, stack2.language_type)
    map(self._VerifyTwoStackFramesEqual, stack1.frames, stack2.frames)

  def _VerifyTwoStacktracesEqual(self, trace1, trace2):
    self.assertIsNotNone(trace1, "the first trace is unexpectedly missing")
    self.assertIsNotNone(trace2, "the second trace is unexpectedly missing")
    self.assertEqual(len(trace1.stacks), len(trace2.stacks))
    map(self._VerifyTwoCallStacksEqual, trace1.stacks, trace2.stacks)
