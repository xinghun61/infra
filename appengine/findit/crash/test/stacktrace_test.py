# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash.callstack import CallStack
from crash.callstack import StackFrame
from crash.stacktrace import Stacktrace

from crash.test.stacktrace_test_suite import StacktraceTestSuite


class StacktraceTest(StacktraceTestSuite):
  def testCrashStackForStacktraceWithoutSignature(self):
    frame_list1 = [
        StackFrame(0, 'src/', '', 'func', 'file0.cc', [32])]

    frame_list2 = [
        StackFrame(0, 'src/', '', 'func2', 'file0.cc', [32])]

    stacktrace = Stacktrace([CallStack(0, frame_list=frame_list1),
                             CallStack(1, frame_list=frame_list2)])
    expected_crash_stack = CallStack(0, frame_list=frame_list1)

    self._VerifyTwoCallStacksEqual(stacktrace.crash_stack, expected_crash_stack)

  def testFilterFramesBeforeSignatureForCrashStack(self):
    frame_list1 = [
        StackFrame(0, 'src/', '', 'func', 'file0.cc', [32]),
    ]
    callstack1 = CallStack(0, frame_list=frame_list1)

    frame_list2 = [
        StackFrame(0, 'src/', '', 'func', 'file0.cc', [32]),
        StackFrame(1, 'src/', '', 'signature_func', 'file1.cc', [53]),
        StackFrame(2, 'src/', '', 'funcc', 'file2.cc', [3])
    ]
    callstack2 = CallStack(0, frame_list=frame_list2)

    stacktrace = Stacktrace([callstack1, callstack2], 'signature')

    expected_frame_list = [
        StackFrame(1, 'src/', '', 'signature_func', 'file1.cc', [53]),
        StackFrame(2, 'src/', '', 'funcc', 'file2.cc', [3])]
    expected_crash_stack = CallStack(0, frame_list=expected_frame_list)

    self._VerifyTwoCallStacksEqual(stacktrace.crash_stack,
                                   expected_crash_stack)

  def testNoSignatureMatchForCrashStack(self):
    frame_list = [
        StackFrame(0, 'src/', '', 'func', 'file0.cc', [32]),
    ]
    callstack = CallStack(0, frame_list=frame_list)

    stacktrace = Stacktrace([callstack], 'signature')

    expected_frame_list = frame_list
    expected_crash_stack = CallStack(0, frame_list=expected_frame_list)

    self._VerifyTwoCallStacksEqual(stacktrace.crash_stack,
                                   expected_crash_stack)

  def testCrashStackFallBackToFirstLeastPriorityCallStack(self):
    stacktrace = Stacktrace()
    self.assertEqual(stacktrace.crash_stack, None)

    callstack_list = [CallStack(0), CallStack(1)]
    stacktrace.extend(callstack_list)

    self._VerifyTwoCallStacksEqual(stacktrace.crash_stack,
                                   callstack_list[0])

  def testInitStacktaceByCopyAnother(self):
    stack_trace = Stacktrace()
    stack_trace.extend([CallStack(0), CallStack(1)])

    self._VerifyTwoStacktracesEqual(Stacktrace(stack_trace), stack_trace)
