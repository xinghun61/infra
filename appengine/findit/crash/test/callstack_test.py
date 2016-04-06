# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.dependency import Dependency
from crash.callstack import StackFrame, CallStack
from crash.test.stacktrace_test_suite import StacktraceTestSuite
from crash.type_enums import CallStackFormatType


class CallStackTest(StacktraceTestSuite):

  def testStackFrameToString(self):
    self.assertEqual(
        StackFrame(0, 'src/', '', 'func', 'f.cc', []).ToString(),
        '#0 in func @ f.cc')
    self.assertEqual(
        StackFrame(0, 'src/', '', 'func', 'f.cc', [1]).ToString(),
        '#0 in func @ f.cc:1')
    self.assertEqual(
        StackFrame(0, 'src/', '', 'func', 'f.cc', [1, 2, 3, 4]).ToString(),
        '#0 in func @ f.cc:1:3')

  def testParseLineForJavaCallstackFormat(self):
    stack = CallStack(0, CallStackFormatType.JAVA)

    stack.ParseLine('dummy line', {})
    self.assertEqual(stack, [])

    deps = {'org/': Dependency('org/', 'https://repo', '1')}
    stack.ParseLine('  at org.a.b(a.java:609)', deps)
    self._VerifyTwoStackFramesEqual(
        stack[0],
        StackFrame(0, 'org/', '', 'org.a.b', 'a.java', [609]))

  def testParseLineForSyzyasanCallstackFormat(self):
    stack = CallStack(0, CallStackFormatType.SYZYASAN)

    stack.ParseLine('dummy line', {})
    self.assertEqual(stack, [])

    deps = {'src/content/': Dependency('src/content/', 'https://repo', '1')}
    stack.ParseLine('c::p::n [src/content/e.cc @ 165]', deps)
    self._VerifyTwoStackFramesEqual(
        stack[0],
        StackFrame(0, 'src/content/', '', 'c::p::n', 'e.cc', [165]))

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
        StackFrame(0, 'tp/webrtc/', '', 'func0', 'a.c', [38, 39, 40, 41]))
