# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.dependency import Dependency
from crash.stacktrace import CallStack
from crash.stacktrace import StackFrame
from crash.stacktrace import Stacktrace
from crash.test.stacktrace_test_suite import StacktraceTestSuite
from crash.type_enums import CallStackFormatType
from crash.type_enums import CallStackLanguageType

class CallStackTest(StacktraceTestSuite):

  def testCallStackBool(self):
    self.assertFalse(CallStack(0))
    frame = StackFrame(0, 'src/', 'func', 'f.cc', 'src/f.cc', [])
    self.assertTrue(CallStack(0, frame_list=[frame]))

  def testCallStackSliceFrames(self):
    frames = [
        StackFrame(0, 'src/', 'func0', 'file0.cc', 'src/file0.cc', [32]),
        StackFrame(1, 'src/', 'func1', 'file1.cc', 'src/file1.cc', [53]),
        StackFrame(2, 'src/', 'func2', 'file2.cc', 'src/file2.cc', [3])]

    self._VerifyTwoCallStacksEqual(
        CallStack(0, frame_list=frames[2:2]),
        CallStack(0, frame_list=frames).SliceFrames(2, 2))
    self._VerifyTwoCallStacksEqual(
        CallStack(0, frame_list=frames[:2]),
        CallStack(0, frame_list=frames).SliceFrames(None, 2))
    self._VerifyTwoCallStacksEqual(
        CallStack(0, frame_list=frames[2:]),
        CallStack(0, frame_list=frames).SliceFrames(2, None))
    self._VerifyTwoCallStacksEqual(
        CallStack(0, frame_list=frames[:]),
        CallStack(0, frame_list=frames).SliceFrames(None, None))

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

    frame = frame._replace(repo_url = 'https://repo_url')
    self.assertEqual(frame.BlameUrl('1'), 'https://repo_url/+blame/1/f.cc')

    frame = frame._replace(crashed_line_numbers = [9, 10])
    self.assertEqual(frame.BlameUrl('1'), 'https://repo_url/+blame/1/f.cc#9')

  def testCallStackConstructorIsLanguageJavaIfFormatJava(self):
    self.assertEqual(
        CallStack(0, format_type = CallStackFormatType.JAVA).language_type,
        CallStackLanguageType.JAVA)

  def testParseStackFrameForJavaCallstackFormat(self):
    language_type = None
    format_type = CallStackFormatType.JAVA
    self.assertIsNone(
        StackFrame.Parse(language_type, format_type, 'dummy line', {}))

    deps = {'org/': Dependency('org/', 'https://repo', '1')}
    frame = StackFrame.Parse(language_type, format_type,
        '  at org.a.b(a.java:609)', deps)
    self._VerifyTwoStackFramesEqual(
        frame,
        StackFrame(0, 'org/', 'org.a.b', 'a.java', 'org/a.java', [609]))

  def testParseStackFrameForSyzyasanCallstackFormat(self):
    language_type = None
    format_type = CallStackFormatType.SYZYASAN
    self.assertIsNone(
        StackFrame.Parse(language_type, format_type, 'dummy line', {}))

    deps = {'src/content/': Dependency('src/content/', 'https://repo', '1')}
    frame = StackFrame.Parse(language_type, format_type,
        'c::p::n [src/content/e.cc @ 165]', deps)
    self._VerifyTwoStackFramesEqual(
        frame,
        StackFrame(
            0, 'src/content/', 'c::p::n', 'e.cc', 'src/content/e.cc', [165]))

  def testParseStackFrameForDefaultCallstackFormat(self):
    language_type = None
    format_type = CallStackFormatType.DEFAULT
    self.assertIsNone(
        StackFrame.Parse(language_type, format_type, 'dummy line', {}))

    deps = {'tp/webrtc/': Dependency('tp/webrtc/', 'https://repo', '1')}
    frame = StackFrame.Parse(language_type, format_type,
        '#0 0x52617a in func0 tp/webrtc/a.c:38:3', deps)
    self._VerifyTwoStackFramesEqual(
        frame,
        StackFrame(
            0, 'tp/webrtc/', 'func0', 'a.c', 'tp/webrtc/a.c', [38, 39, 40, 41]))

    frame = StackFrame.Parse(language_type, format_type,
        '#1 0x526 in func::func2::func3 tp/webrtc/a.c:3:2', deps)
    self._VerifyTwoStackFramesEqual(
        frame,
        StackFrame(
            1, 'tp/webrtc/', 'func::func2::func3', 'a.c', 'tp/webrtc/a.c',
            [3, 4, 5]))

  def testParseStackFrameForFracasJavaStack(self):
    format_type = CallStackFormatType.DEFAULT
    language_type = CallStackLanguageType.JAVA

    frame = StackFrame.Parse(language_type, format_type,
        '#0 0xxx in android.app.func app.java:2450', {})
    self._VerifyTwoStackFramesEqual(
        frame,
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
    stacktrace = Stacktrace(stack_list=callstack_list)

    self._VerifyTwoCallStacksEqual(stacktrace.crash_stack,
                                   callstack_list[0])

  def testInitStacktaceByCopyAnother(self):
    stack_trace = Stacktrace(stack_list=[CallStack(0), CallStack(1)])

    self._VerifyTwoStacktracesEqual(Stacktrace(stack_trace), stack_trace)
