# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash import callstack_detectors
from crash.flag_manager import ParsingFlag
from crash.flag_manager import FlagManager
from crash.test.stacktrace_test_suite import StacktraceTestSuite
from crash.type_enums import CallStackFormatType
from crash.type_enums import LanguageType


class CallStackDetectorTest(StacktraceTestSuite):

  def testAndroidJobDetector(self):
    """Tests that ``AndroidJobDetector`` detects android job callstack."""
    stack_detector = callstack_detectors.AndroidJobDetector()
    flag_manager = FlagManager()
    flag_manager.Register('group',
                          ParsingFlag('java_main_stack_flag', value=True))

    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack(
            'java.lang.IllegalStateException: blabla', flag_manager),
        (True, 0, CallStackFormatType.JAVA, LanguageType.JAVA, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack(
            'org.chromium.src.BlaBla', flag_manager),
        (True, 1, CallStackFormatType.JAVA, LanguageType.JAVA, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('Caused by:', flag_manager),
        (True, 1, CallStackFormatType.JAVA, LanguageType.JAVA, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack(
            'com.google.android.BlaBla', flag_manager),
        (True, 1, CallStackFormatType.JAVA, LanguageType.JAVA, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('dummy', flag_manager),
        (False, None, None, None, None))

  def testSyzyasanDetector(self):
    """Tests that ``SyzyasanDetector`` detects sysyasn callstack."""
    stack_detector = callstack_detectors.SyzyasanDetector()
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('Crash stack:'),
        (True, 0, CallStackFormatType.SYZYASAN, LanguageType.CPP, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('A stack:'),
        (True, 1, CallStackFormatType.SYZYASAN, LanguageType.CPP, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('dummy'),
        (False, None, None, None, None))

  def testTsanDetector(self):
    """Tests that ``TsanDetector`` detects thread sanitizer callstack."""
    stack_detector = callstack_detectors.TsanDetector()
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('Read of size 1023:'),
        (True, 0, CallStackFormatType.DEFAULT, LanguageType.CPP, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('WARNING: ThreadSanitizer'),
        (True, 0, CallStackFormatType.DEFAULT, LanguageType.CPP, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('Previous read of size 102'),
        (True, 1, CallStackFormatType.DEFAULT, LanguageType.CPP, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack(
            'Location is heap block of size 3543'),
        (True, 1, CallStackFormatType.DEFAULT, LanguageType.CPP, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('dummy'),
        (False, None, None, None, None))

  def testUbsanDetector(self):
    """Tests that ``UbsanDetector`` detects ubsan callstack."""
    stack_detector = callstack_detectors.UbsanDetector()
    flag_manager = FlagManager()
    flag_manager.Register('group',
                          ParsingFlag('is_first_stack_flag', value=True))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('blabla: runtime error: blabla',
                                             flag_manager),
        (True, 0, CallStackFormatType.DEFAULT, LanguageType.CPP, {}))
    # After the ``is_first_stack_flag`` is set to False, the priority will be
    # 1.
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('blabla: runtime error: blabla',
                                             flag_manager),
        (True, 1, CallStackFormatType.DEFAULT, LanguageType.CPP, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('dummy', flag_manager),
        (False, None, None, None, None))

  def testMsanDetector(self):
    """Tests that ``MsanDetector`` detects memory sanitizer callstack."""
    stack_detector = callstack_detectors.MsanDetector()
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack(
            'Uninitialized value was created by'),
        (True, 0, CallStackFormatType.DEFAULT, LanguageType.CPP, {}))
    # After the ``is_first_stack_flag`` is set to False, the priority will be
    # 1.
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack(
            'Uninitialized value was stored to'),
        (True, 1, CallStackFormatType.DEFAULT, LanguageType.CPP, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack(
            '==123== ERROR:MemorySanitizer'),
        (True, 2, CallStackFormatType.DEFAULT, LanguageType.CPP, {'pid': 123}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('dummy'),
        (False, None, None, None, None))

  def testAsanDetector(self):
    """Tests that ``AsanDetector`` detects address sanitizer callstack."""
    stack_detector = callstack_detectors.AsanDetector()
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('==123== ERROR:AddressSanitizer'),
        (True, 0, CallStackFormatType.DEFAULT, LanguageType.CPP, {'pid': 123}))
    # After the ``is_first_stack_flag`` is set to False, the priority will be
    # 1.
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('READ of size 32 at backtrace:'),
        (True, 0, CallStackFormatType.DEFAULT, LanguageType.CPP, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('freed by thread T99 here:'),
        (True, 1, CallStackFormatType.DEFAULT, LanguageType.CPP, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack(
            'previously allocated by thread T1 here:'),
        (True, 1, CallStackFormatType.DEFAULT, LanguageType.CPP, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('Thread T9 created by'),
        (True, 1, CallStackFormatType.DEFAULT, LanguageType.CPP, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('dummy'),
        (False, None, None, None, None))

  def testChromeCrashDetector(self):
    """Tests that ``ChromeCrashDetector`` detects Fracas/Cracas callstack."""
    stack_detector = callstack_detectors.ChromeCrashStackDetector()

    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('CRASHED [EXC @ 0x508]'),
        (True, 0, CallStackFormatType.DEFAULT, LanguageType.CPP, {}))
    self.assertTupleEqual(
        stack_detector.IsStartOfNewCallStack('(JAVA) CRASHED [EXC @ 0x508]'),
        (True, 0, CallStackFormatType.DEFAULT, LanguageType.JAVA, {}))
    self.assertTupleEqual(stack_detector.IsStartOfNewCallStack('dummy line'),
                          (False, None, None, None, None))
