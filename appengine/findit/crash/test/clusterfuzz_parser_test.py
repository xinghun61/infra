# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import textwrap

from crash import callstack_detectors
from crash.clusterfuzz_parser import ClusterfuzzParser
from crash.clusterfuzz_parser import GetCallStackDetector
from crash.stacktrace import StackFrame
from crash.stacktrace import CallStack
from crash.stacktrace import Stacktrace
from crash.test.stacktrace_test_suite import StacktraceTestSuite
from crash.type_enums import CallStackFormatType
from crash.type_enums import LanguageType
from crash.type_enums import SanitizerType
from libs.deps.dependency import Dependency


class ClusterfuzzParserTest(StacktraceTestSuite):

  def testGetCallStackDetector(self):
    self.assertTrue(isinstance(GetCallStackDetector('android_job', None),
                               callstack_detectors.AndroidJobDetector))
    self.assertTrue(
        isinstance(GetCallStackDetector('job', SanitizerType.SYZYASAN),
                   callstack_detectors.SyzyasanDetector))
    self.assertTrue(
        isinstance(GetCallStackDetector('job', SanitizerType.THREAD_SANITIZER),
                   callstack_detectors.TsanDetector))
    self.assertTrue(
        isinstance(GetCallStackDetector('job', SanitizerType.UBSAN),
                   callstack_detectors.UbsanDetector))
    self.assertTrue(
        isinstance(GetCallStackDetector('job', SanitizerType.MEMORY_SANITIZER),
                   callstack_detectors.MsanDetector))
    self.assertTrue(
        isinstance(GetCallStackDetector('job', SanitizerType.ADDRESS_SANITIZER),
                   callstack_detectors.AsanDetector))
    self.assertIsNone(GetCallStackDetector('job', None))

  def testReturnNoneForEmptyString(self):
    parser = ClusterfuzzParser()
    deps = {'src/': Dependency('src/', 'https://repo', '1')}

    self.assertIsNone(parser.Parse('', deps, 'asan_job',
                                   SanitizerType.ADDRESS_SANITIZER))

  def testReturnNoneForDummyJobType(self):
    parser = ClusterfuzzParser()
    deps = {'src/': Dependency('src/', 'https://repo', '1')}

    self.assertIsNone(parser.Parse('Crash stack:', deps, 'dummy_job', None))

  def testChromeCrashParserParseLineMalformatedCallstack(self):
    parser = ClusterfuzzParser()
    deps = {'src/': Dependency('src/', 'https://repo', '1')}
    stacktrace_string = textwrap.dedent(
        """
        Blabla...
        ==1==ERROR: AddressSanitizer: stack-overflow on address 0x7ffec59ebec0
        #0 dummy
        #1 dummy
        #2 dummy
        """
    )
    self.assertIsNone(parser.Parse(stacktrace_string, deps, 'asan_job',
                                   SanitizerType.ADDRESS_SANITIZER))

  def testClusterfuzzParserParseStacktrace(self):
    parser = ClusterfuzzParser()
    deps = {'src/': Dependency('src/', 'https://repo', '1')}
    stacktrace_string = textwrap.dedent(
        """
        Blabla...
        ==1==ERROR: AddressSanitizer: stack-overflow on address 0x7ffec59ebec0
        #0 0x7f5b944a37bb in a::aa(p* d) src/a.h:225
        #1 0x7f5b9449a880 in b::bb(p* d) src/b.h:266:1
        #2 0x7f5b9449a880 in c::cc(p* d) src/c.h:281
        """
    )

    stacktrace = parser.Parse(stacktrace_string, deps, 'asan_job',
                              SanitizerType.ADDRESS_SANITIZER)
    stack = CallStack(0, frame_list=[
        StackFrame(0, 'src/', 'a::aa(p* d)', 'a.h', 'src/a.h', [225]),
        StackFrame(1, 'src/', 'b::bb(p* d)', 'b.h', 'src/b.h', [266, 267]),
        StackFrame(2, 'src/', 'c::cc(p* d)', 'c.h', 'src/c.h', [281])])
    expected_stacktrace = Stacktrace([stack], stack)

    self._VerifyTwoStacktracesEqual(stacktrace, expected_stacktrace)
