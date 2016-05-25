# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash.callstack import StackFrame, CallStack
from crash import callstack_filters
from crash.test.stacktrace_test_suite import StacktraceTestSuite


class CallStackFiltersTest(StacktraceTestSuite):

  def testFilterInlineFunctionFrames(self):
    frame_list = [
        StackFrame(
            0, 'src/', 'normal_func', 'f.cc', 'dummy/src/f.cc', [2]),
        StackFrame(
            0, 'src/', 'inline_func',
            'third_party/llvm-build/Release+Asserts/include/c++/v1/a',
            'src/third_party/llvm-build/Release+Asserts/include/c++/v1/a', [1]),
        StackFrame(
            0, 'src/', 'inline_func',
            'linux/debian_wheezy_amd64-sysroot/usr/include/c++/4.6/bits/b',
            'src/linux/debian_wheezy_amd64-sysroot/usr/include/c++/4.6/bits/b',
            [1]),
        StackFrame(
            0, 'src/', 'inline_func',
            'eglibc-3GlaMS/eglibc-2.19/sysdeps/unix/c',
            'src/eglibc-3GlaMS/eglibc-2.19/sysdeps/unix/c', [1])
    ]

    expected_frame_list = frame_list[:1]

    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterInlineFunctionFrames(
            CallStack(0, frame_list=frame_list)),
        CallStack(0, frame_list=expected_frame_list))
