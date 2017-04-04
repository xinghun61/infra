# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import textwrap

from crash.chromecrash_parser import ChromeCrashParser
from crash.stacktrace import StackFrame
from crash.stacktrace import CallStack
from crash.stacktrace import Stacktrace
from crash.test.stacktrace_test_suite import StacktraceTestSuite
from crash.type_enums import CallStackFormatType
from crash.type_enums import LanguageType
from libs.deps.dependency import Dependency


class ChromeCrashParserTest(StacktraceTestSuite):

  def testReturnEmptyStacktraceForEmptyString(self):
    parser = ChromeCrashParser()
    deps = {'src/': Dependency('src/', 'https://repo', '1')}

    self.assertIsNone(parser.Parse('', deps))

  def testChromeCrashParserParseLineMalformatedCallstack(self):
    parser = ChromeCrashParser()
    deps = {'src/': Dependency('src/', 'https://repo', '1')}
    stacktrace_string = textwrap.dedent(
        """
        CRASHED [EXC @ 0x508]
        #0 [RESTRICTED]
        #1 [RESTRICTED]
        """
    )
    self.assertIsNone(parser.Parse(stacktrace_string, deps))

  def testChromeCrashParserParseLineOneCallstack(self):
    parser = ChromeCrashParser()
    deps = {'src/': Dependency('src/', 'https://repo', '1')}
    stacktrace_string = textwrap.dedent(
        """
        CRASHED [EXC @ 0x508]
        #0 0x7fee in a::c(p* &d) src/f0.cc:177
        #1 0x4b6e in a::d(a* c) src/f1.cc:227
        #2 0x7ff9 in a::e(int) src/f2.cc:87:1
        """
    )

    stacktrace = parser.Parse(stacktrace_string, deps)

    stack = CallStack(0, frame_list=[
        StackFrame(0, 'src/', 'a::c(p* &d)', 'f0.cc', 'src/f0.cc', [177]),
        StackFrame(1, 'src/', 'a::d(a* c)', 'f1.cc', 'src/f1.cc', [227]),
        StackFrame(2, 'src/', 'a::e(int)', 'f2.cc', 'src/f2.cc', [87, 88])])
    expected_stacktrace = Stacktrace([stack], stack)

    self._VerifyTwoStacktracesEqual(stacktrace, expected_stacktrace)

  def testChromeCrashParserParseLineJavaCallstack(self):
    parser = ChromeCrashParser()
    deps = {'src/': Dependency('src/', 'https://repo', '1')}
    stacktrace_string = textwrap.dedent(
        """
        (JAVA) CRASHED [EXC @ 0x508]
        #0 0x7fee in a.f0.c f0.java:177
        #1 0x4b6e in org.chromium.chrome.browser.a.f1.d f1.java:227
        #2 0x7ff9 in a.f2.e f2.java:87:1
        """
    )

    stacktrace = parser.Parse(stacktrace_string, deps)
    stack = CallStack(0,
        language_type=LanguageType.JAVA,
        frame_list=[
            StackFrame(0, '', 'a.f0.c', 'a/f0.java', 'a/f0.java', [177]),
            StackFrame(
                1, 'src/', 'org.chromium.chrome.browser.a.f1.d',
                'chrome/android/java/src/org/chromium/chrome/browser/a/f1.java',
                'src/chrome/android/java/src/org/chromium/chrome/'
                'browser/a/f1.java',
                [227]),
            StackFrame(2, '', 'a.f2.e', 'a/f2.java', 'a/f2.java', [87, 88])])
    expected_stacktrace = Stacktrace([stack], stack)

    self._VerifyTwoStacktracesEqual(stacktrace, expected_stacktrace)

  def testChromeCrashParserParseLineMultipleCallstacks(self):
    parser = ChromeCrashParser()
    deps = {'src/': Dependency('src/', 'https://repo', '1')}
    stacktrace_string = textwrap.dedent(
        """
        CRASHED [EXC @ 0x66]
        #0 0x7fee in a::b::c(p* &d) src/f0.cc:177
        #1 0x4b6e in a::b::d(a* c) src/f1.cc:227

        CRASHED [EXC @ 0x508]
        #0 0x8fee in e::f::g(p* &d) src/f.cc:20:2
        #1 0x1fae in h::i::j(p* &d) src/ff.cc:9:1
        """
    )

    stacktrace = parser.Parse(stacktrace_string, deps)

    expected_callstack0 = CallStack(0, frame_list=[
        StackFrame(0, 'src/', 'a::b::c(p* &d)', 'f0.cc', 'src/f0.cc', [177]),
        StackFrame(1, 'src/', 'a::b::d(a* c)', 'f1.cc', 'src/f1.cc', [227])])
    expected_callstack1 = CallStack(0, frame_list=[
        StackFrame(
            0, 'src/', 'e::f::g(p* &d)', 'f.cc', 'src/f.cc', [20, 21, 22]),
        StackFrame(
            1, 'src/', 'h::i::j(p* &d)', 'ff.cc', 'src/ff.cc', [9, 10])])

    expected_stacktrace = Stacktrace([expected_callstack0, expected_callstack1],
                                     expected_callstack0)
    self._VerifyTwoStacktracesEqual(stacktrace, expected_stacktrace)
