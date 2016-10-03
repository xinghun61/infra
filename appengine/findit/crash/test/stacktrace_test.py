# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.dependency import Dependency
from crash.stacktrace import StackFrame
from crash.stacktrace import CallStack
from crash.stacktrace import Stacktrace
from crash.test.stacktrace_test_suite import StacktraceTestSuite
from crash.type_enums import CallStackFormatType
from crash.type_enums import CallStackLanguageType


class CallStackTest(StacktraceTestSuite):

  def testStackFrameToString(self):
    self.assertEqual(
        StackFrame(0, 'src/', 'func', 'f.cc', 'src/f.cc', []).ToString(),
        '#0 in func @ f.cc')
    self.assertEqual(
        StackFrame(0, 'src/', 'func', 'f.cc', 'src/f.cc', [1]).ToString(),
        '#0 in func @ f.cc:1')
    self.assertEqual(
        StackFrame(0, 'src/', 'func', 'f.cc', 'src/f.cc', [1, 2]).ToString(),
        '#0 in func @ f.cc:1:1')

  def testBlameUrlForStackFrame(self):
    frame = StackFrame(0, 'src/', 'func', 'f.cc', 'src/f.cc', [])
    self.assertEqual(frame.BlameUrl('1'), None)

    frame.repo_url = 'https://repo_url'
    self.assertEqual(frame.BlameUrl('1'), 'https://repo_url/+blame/1/f.cc')

    frame.crashed_line_numbers = [9, 10]
    self.assertEqual(frame.BlameUrl('1'), 'https://repo_url/+blame/1/f.cc#9')

  def testFrameListInitCallStack(self):
    stack = CallStack(0)
    stack.extend([StackFrame(0, 'src/', '', 'func', 'f.cc', [2])])

    copy_stack = CallStack(stack.priority, frame_list=stack)
    self._VerifyTwoCallStacksEqual(copy_stack, stack)

  def testParseLineForJavaCallstackFormat(self):
    stack = CallStack(0, CallStackFormatType.JAVA)

    stack.ParseLine('dummy line', {})
    self.assertEqual(stack, [])

    deps = {'org/': Dependency('org/', 'https://repo', '1')}
    stack.ParseLine('  at org.a.b(a.java:609)', deps)
    self._VerifyTwoStackFramesEqual(
        stack[0],
        StackFrame(0, 'org/', 'org.a.b', 'a.java', 'org/a.java', [609]))

  def testParseLineForSyzyasanCallstackFormat(self):
    stack = CallStack(0, CallStackFormatType.SYZYASAN)

    stack.ParseLine('dummy line', {})
    self.assertEqual(stack, [])

    deps = {'src/content/': Dependency('src/content/', 'https://repo', '1')}
    stack.ParseLine('c::p::n [src/content/e.cc @ 165]', deps)
    self._VerifyTwoStackFramesEqual(
        stack[0],
        StackFrame(
            0, 'src/content/', 'c::p::n', 'e.cc', 'src/content/e.cc', [165]))

  def testParseLineForDefaultCallstackFormat(self):
    stack = CallStack(0, CallStackFormatType.DEFAULT)

    stack.ParseLine('dummy line', {})
    self.assertEqual(stack, [])

    stack.ParseLine('#dummy line', {})
    self.assertEqual(stack, [])

    deps = {'tp/webrtc/': Dependency('tp/webrtc/', 'https://repo', '1')}
    stack.ParseLine('#0 0x52617a in func0 tp/webrtc/a.c:38:3', deps)
    self._VerifyTwoStackFramesEqual(
        stack[0],
        StackFrame(
            0, 'tp/webrtc/', 'func0', 'a.c', 'tp/webrtc/a.c', [38, 39, 40, 41]))

    stack.ParseLine('#1 0x526 in func::func2::func3 tp/webrtc/a.c:3:2', deps)
    self._VerifyTwoStackFramesEqual(
        stack[1],
        StackFrame(
            1, 'tp/webrtc/', 'func::func2::func3', 'a.c', 'tp/webrtc/a.c',
            [3, 4, 5]))

  def testParseLineForFracasJavaStack(self):
    stack = CallStack(0, CallStackFormatType.DEFAULT,
                      CallStackLanguageType.JAVA)

    stack.ParseLine('#0 0xxx in android.app.func app.java:2450', {})
    self._VerifyTwoStackFramesEqual(
        stack[0],
        StackFrame(
            0, '', 'android.app.func', 'android/app.java',
            'android/app.java', [2450]))


class StacktraceTest(StacktraceTestSuite):

  def testCrashStackForStacktraceWithoutSignature(self):
    frame_list1 = [
        StackFrame(0, 'src/', 'func', 'file0.cc', 'src/file0.cc', [32])]

    frame_list2 = [
        StackFrame(0, 'src/', 'func2', 'file0.cc', 'src/file0.cc', [32])]

    stacktrace = Stacktrace([CallStack(0, frame_list=frame_list1),
                             CallStack(1, frame_list=frame_list2)])
    expected_crash_stack = CallStack(0, frame_list=frame_list1)

    self._VerifyTwoCallStacksEqual(stacktrace.crash_stack, expected_crash_stack)

  def testFilterFramesBeforeSignatureForCrashStack(self):
    frame_list1 = [
        StackFrame(0, 'src/', 'func', 'file0.cc', 'src/file0.cc', [32]),
    ]
    callstack1 = CallStack(0, frame_list=frame_list1)

    frame_list2 = [
        StackFrame(0, 'src/', 'func', 'file0.cc', 'src/file0.cc', [32]),
        StackFrame(1, 'src/', 'signature_func',
                   'file1.cc', 'src/file1.cc', [53]),
        StackFrame(2, 'src/', 'funcc', 'file2.cc', 'src/file2.cc', [3])
    ]
    callstack2 = CallStack(0, frame_list=frame_list2)

    stacktrace = Stacktrace([callstack1, callstack2], 'signature')

    expected_frame_list = [
        StackFrame(
            1, 'src/', 'signature_func', 'file1.cc', 'src/file1.cc', [53]),
        StackFrame(
            2, 'src/', 'funcc', 'file2.cc', 'src/file2.cc', [3])]
    expected_crash_stack = CallStack(0, frame_list=expected_frame_list)

    self._VerifyTwoCallStacksEqual(stacktrace.crash_stack,
                                   expected_crash_stack)

  def testNoSignatureMatchForCrashStack(self):
    frame_list = [
        StackFrame(0, 'src/', 'func', 'file0.cc', 'src/file0.cc', [32]),
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
