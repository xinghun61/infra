# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash.stacktrace import StackFrame
from crash.stacktrace import CallStackBuffer
from crash import callstack_filters
from crash.test.stacktrace_test_suite import StacktraceTestSuite


class CallStackFiltersTest(StacktraceTestSuite):

  def testFilterInlineFunction(self):
    """Tests ``FilterInlineFunction`` filters all inline function frames."""
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
        callstack_filters.FilterInlineFunction()(
            CallStackBuffer(0, frame_list=frame_list)),
        CallStackBuffer(0, frame_list=expected_frame_list))

  def testKeepTopNFrames(self):
    """Tests ``KeepTopNFrames`` only keeps the top n frames of a callstack."""
    frame_list = [
        StackFrame(
            0, 'src/', 'normal_func', 'f.cc', 'dummy/src/f.cc', [2]),
        StackFrame(
            0, 'src/', 'func', 'a.cc', 'a.cc', [1]),
    ]

    top_n = 1
    self._VerifyTwoCallStacksEqual(
        callstack_filters.KeepTopNFrames(top_n)(
            CallStackBuffer(0, frame_list=frame_list)),
        CallStackBuffer(0, frame_list=frame_list[:top_n]))

  def testKeepTopNFramesDoNothingForNonTopNFrames(self):
    """Tests ``KeepTopNFrames`` does nothing if top_n_frames is None"""
    frame_list = [
        StackFrame(
            0, 'src/', 'normal_func', 'f.cc', 'dummy/src/f.cc', [2]),
        StackFrame(
            0, 'src/', 'func', 'a.cc', 'a.cc', [1]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    self._VerifyTwoCallStacksEqual(
        callstack_filters.KeepTopNFrames()(stack_buffer), stack_buffer)
