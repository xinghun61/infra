# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis import callstack_filters
from analysis.analysis_testcase import AnalysisTestCase
from analysis.stacktrace import CallStackBuffer
from analysis.stacktrace import StackFrame
from analysis.stacktrace_parser import StacktraceParser


class DummyFilter(callstack_filters.CallStackFilter):

  def __call__(self, stack_buffer):  # pragma: no cover
    return stack_buffer


class StacktraceParserTest(AnalysisTestCase):

  def testFilterInfinityPriorityStackBuffer(self):
    """Tests ``FilterStackBuffer`` return None for inf priority stack buffer."""
    stack_buffer = CallStackBuffer(priority=float('inf'))
    self.assertIsNone(StacktraceParser.FilterStackBuffer(stack_buffer,
                                                         [DummyFilter()]))

  def testFilterEmptyStackBuffer(self):
    """Tests ``FilterStackBuffer`` return None for empty stack buffer."""
    stack_buffer = CallStackBuffer(frame_list=[])
    self.assertIsNone(StacktraceParser.FilterStackBuffer(stack_buffer,
                                                         [DummyFilter()]))

  def testFilterAllFrames(self):
    """Tests ``FilterStackBuffer`` filters all frames and resturn None."""
    frame_list = [
        StackFrame(0, 'src/', 'func', 'file0.cc', 'src/file0.cc', [32]),
        StackFrame(0, 'src/', 'func2', 'file0.cc', 'src/file0.cc', [32])]
    stack_buffer = CallStackBuffer(0, frame_list=frame_list)

    def _MockFilter(stack_buffer):
      stack_buffer.frames = None
      return stack_buffer

    self.assertIsNone(StacktraceParser.FilterStackBuffer(
        stack_buffer,
        filters=[_MockFilter]))

  def testFilterSomeFrames(self):
    """Tests ``FilterStackBuffer`` filters some frames."""
    frame_list = [
        StackFrame(0, 'src/', 'func', 'file0.cc', 'src/file0.cc', [32]),
        StackFrame(0, 'src/', 'func2', 'file0.cc', 'src/file0.cc', [32])]
    stack_buffer = CallStackBuffer(0, frame_list=frame_list)

    def _MockFilter(stack):
      stack.frames = stack.frames[:1]
      return stack

    self._VerifyTwoCallStacksEqual(
        StacktraceParser.FilterStackBuffer(stack_buffer, filters=[_MockFilter]),
        CallStackBuffer(stack_buffer.priority, frame_list=frame_list[:1]))
