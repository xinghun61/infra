# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash.callstack import CallStack
from crash.stacktrace import Stacktrace
from crash.test.crash_test_suite import CrashTestSuite


class StacktraceTest(CrashTestSuite):

  def testGetCrashStack(self):
    stack_trace = Stacktrace()
    self.assertEqual(stack_trace.GetCrashStack(), None)

    callstack_list = [CallStack(0), CallStack(1)]
    stack_trace.extend(callstack_list)

    self._VerifyTwoCallStacksEqual(stack_trace.GetCrashStack(),
                                   callstack_list[0])

  def testInitStacktaceByCopyAnother(self):
    stack_trace = Stacktrace()
    stack_trace.extend([CallStack(0), CallStack(1)])

    self._VerifyTwoStacktracesEqual(Stacktrace(stack_trace), stack_trace)
