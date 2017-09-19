# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import textwrap

from analysis import callstack_detectors
from analysis.analysis_testcase import AnalysisTestCase
from analysis.clusterfuzz_parser import ClusterfuzzParser
from analysis.clusterfuzz_parser import GetCallStackDetectors
from analysis.stacktrace import StackFrame
from analysis.stacktrace import CallStack
from analysis.stacktrace import Stacktrace
from analysis.type_enums import CallStackFormatType
from analysis.type_enums import CrashType
from analysis.type_enums import LanguageType
from analysis.type_enums import SanitizerType
from libs.deps.dependency import Dependency


class ClusterfuzzParserTest(AnalysisTestCase):

  def testGetCallStackDetectors(self):
    self.assertTrue(
        isinstance(GetCallStackDetectors('android_job', 'abrt')[0],
        callstack_detectors.AndroidJobDetector))
    self.assertTrue(
        isinstance(GetCallStackDetectors('job', CrashType.DIRECT_LEAK)[0],
                   callstack_detectors.DirectLeakDetector))
    self.assertTrue(
        isinstance(GetCallStackDetectors('job', CrashType.INDIRECT_LEAK)[0],
                   callstack_detectors.IndirectLeakDetector))
    self.assertTrue(
        isinstance(GetCallStackDetectors('job', 'abrt')[0],
                   callstack_detectors.AsanDetector))

    self.assertTrue(
        isinstance(GetCallStackDetectors('job', 'abrt')[1],
                   callstack_detectors.MsanDetector))

    self.assertTrue(
        isinstance(GetCallStackDetectors('job', 'abrt')[2],
                   callstack_detectors.SyzyasanDetector))

    self.assertTrue(
        isinstance(GetCallStackDetectors('job', 'abrt')[3],
                   callstack_detectors.UbsanDetector))

    self.assertTrue(
        isinstance(GetCallStackDetectors('job', 'abrt')[4],
                   callstack_detectors.LibFuzzerDetector))

    self.assertTrue(
        isinstance(GetCallStackDetectors('job', 'abrt')[5],
                   callstack_detectors.TsanDetector))

  def testReturnNoneForEmptyString(self):
    parser = ClusterfuzzParser()
    deps = {'src': Dependency('src', 'https://repo', '1')}

    self.assertIsNone(parser.Parse('', deps, 'asan_job', 'abrt'))

  def testReturnNoneForDummyJobType(self):
    parser = ClusterfuzzParser()
    deps = {'src': Dependency('src', 'https://repo', '1')}

    self.assertIsNone(parser.Parse('Crash stack:', deps, 'dummy_job', 'abrt'))

  def testChromeCrashParserParseLineMalformatedCallstack(self):
    parser = ClusterfuzzParser()
    deps = {'src': Dependency('src', 'https://repo', '1')}
    stacktrace_string = textwrap.dedent(
        """
        Blabla...
        ==1==ERROR: AddressSanitizer: stack-overflow on address 0x7ffec59ebec0
        #0 dummy
        #1 dummy
        #2 dummy
        """
    )
    self.assertIsNone(parser.Parse(stacktrace_string, deps, 'asan_job', 'abrt'))

  def testClusterfuzzParserParseStacktrace(self):
    parser = ClusterfuzzParser()
    deps = {'src': Dependency('src', 'https://repo', '1')}
    stacktrace_string = textwrap.dedent(
        """
        Blabla...
        ==1==ERROR: AddressSanitizer: stack-overflow on address 0x7ffec59ebec0
        #0 0x7f5b944a37bb in a::aa(p* d) src/a.h:225
        #1 0x7f5b9449a880 in b::bb(p* d) src/b.h:266:1
        #2 0x7f5b9449a880 in c::cc(p* d) src/c.h:281
        """
    )

    stacktrace = parser.Parse(stacktrace_string, deps, 'asan_job', 'abrt')
    stack = CallStack(0, frame_list=[
        StackFrame(0, 'src', 'a::aa(p* d)', 'a.h', 'src/a.h', [225]),
        StackFrame(1, 'src', 'b::bb(p* d)', 'b.h', 'src/b.h', [266, 267]),
        StackFrame(2, 'src', 'c::cc(p* d)', 'c.h', 'src/c.h', [281])])
    expected_stacktrace = Stacktrace([stack], stack)

    self._VerifyTwoStacktracesEqual(stacktrace, expected_stacktrace)
