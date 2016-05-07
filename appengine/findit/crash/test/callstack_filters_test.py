# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy

from crash.callstack import StackFrame, CallStack
from crash import callstack_filters
from crash.test.stacktrace_test_suite import StacktraceTestSuite


class CallStackFiltersTest(StacktraceTestSuite):

  def testEmptyFilterFramesBeforeSignature(self):
    callstack = CallStack(0)
    filtered_callstack = copy.copy(callstack)
    callstack_filters.FilterFramesBeforeSignature(filtered_callstack, '')

    self._VerifyTwoCallStacksEqual(callstack, filtered_callstack)

  def testFilterFramesBeforeSignature(self):
    callstack = CallStack(0)
    callstack.extend(
        [StackFrame(0, 'src/', '', 'func', 'file0.cc', [32]),
         StackFrame(0, 'src/', '', 'signature_func', 'file1.cc', [53]),
         StackFrame(0, 'src/', '', 'funcc', 'file2.cc', [3])])

    filtered_callstack = copy.copy(callstack)
    callstack_filters.FilterFramesBeforeSignature(
        filtered_callstack, 'signature')

    expected_callstack = CallStack(0)
    expected_callstack.extend(
        [StackFrame(0, 'src/', '', 'signature_func', 'file1.cc', [53]),
         StackFrame(0, 'src/', '', 'funcc', 'file2.cc', [3])])

    self._VerifyTwoCallStacksEqual(filtered_callstack, expected_callstack)
