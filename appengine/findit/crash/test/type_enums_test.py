# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash.test.stacktrace_test_suite import StacktraceTestSuite
from crash.type_enums import SanitizerType


class TypeEnumsTest(StacktraceTestSuite):

  def testGetSanitizerTypeFromJobType(self):
    """Tests getting SanitizerType from job type."""
    self.assertEqual(SanitizerType.GetSanitizerType('syzyasan_job', 'dummy'),
                     SanitizerType.SYZYASAN)
    self.assertEqual(SanitizerType.GetSanitizerType('ubsan_job', 'dummy'),
                     SanitizerType.UBSAN)
    self.assertEqual(SanitizerType.GetSanitizerType('asan_job', 'dummy'),
                     SanitizerType.ADDRESS_SANITIZER)
    self.assertEqual(SanitizerType.GetSanitizerType('msan_job', 'dummy'),
                     SanitizerType.MEMORY_SANITIZER)
    self.assertEqual(SanitizerType.GetSanitizerType('tsan_job', 'dummy'),
                     SanitizerType.THREAD_SANITIZER)

  def testGetSanitizerTypeFromStacktraceString(self):
    """Tests getting SanitizerType from stacktrace string."""
    self.assertEqual(SanitizerType.GetSanitizerType('dummy_job',
                                                    'AddressSanitizer: dummy'),
                     SanitizerType.ADDRESS_SANITIZER)
    self.assertEqual(SanitizerType.GetSanitizerType('dummy_job',
                                                    'ThreadSanitizer: dummy'),
                     SanitizerType.THREAD_SANITIZER)
    self.assertEqual(SanitizerType.GetSanitizerType('dummy_job',
                                                    'MemorySanitizer: dummy'),
                     SanitizerType.MEMORY_SANITIZER)
    self.assertEqual(SanitizerType.GetSanitizerType('dummy_job',
                                                    'syzyasan: dummy'),
                     SanitizerType.SYZYASAN)
    self.assertEqual(SanitizerType.GetSanitizerType('dummy_job',
                                                    ': runtime error: dummy'),
                     SanitizerType.UBSAN)
    self.assertEqual(SanitizerType.GetSanitizerType('dummy_job', 'dummy'),
                     SanitizerType.UNSUPPORTED)
