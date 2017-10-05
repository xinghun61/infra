# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis import callstack_filters
from analysis.analysis_testcase import AnalysisTestCase
from analysis.stacktrace import StackFrame
from analysis.stacktrace import CallStackBuffer
from analysis.type_enums import LanguageType


class FilterInlineFunctionTest(AnalysisTestCase):
  """Tests that ``FilterInlineFunction`` works as expected."""

  def testFilterInlineFunctions(self):
    """Tests that filtering all inline function frames."""
    frame_list = [
        StackFrame(
            0, 'src/', 'normal_func', 'f.cc', 'dummy/src/f.cc', [2]),
        StackFrame(
            1, 'src/', 'inline_func',
            'third_party/llvm-build/Release+Asserts/include/c++/v1/a',
            'src/third_party/llvm-build/Release+Asserts/include/c++/v1/a', [1]),
        StackFrame(
            2, 'src/', 'inline_func',
            'linux/debian_wheezy_amd64-sysroot/usr/include/c++/4.6/bits/b',
            'src/linux/debian_wheezy_amd64-sysroot/usr/include/c++/4.6/bits/b',
            [1]),
        StackFrame(
            3, 'src/', 'inline_func',
            'eglibc-3GlaMS/eglibc-2.19/sysdeps/unix/c',
            'src/eglibc-3GlaMS/eglibc-2.19/sysdeps/unix/c', [1])
    ]

    expected_frame_list = frame_list[:1]

    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterInlineFunction()(
            CallStackBuffer(0, frame_list=frame_list)),
        CallStackBuffer(0, frame_list=expected_frame_list))


class KeepTopNFramesTest(AnalysisTestCase):
  """Tests that ``KeepTopNFrames`` works as expected."""

  def testKeepTopNFrames(self):
    """Tests that keeping the top n frames of a callstack."""
    frame_list = [
        StackFrame(
            0, 'src/', 'normal_func', 'f.cc', 'dummy/src/f.cc', [2]),
        StackFrame(
            1, 'src/', 'func', 'a.cc', 'a.cc', [1]),
    ]

    top_n = 1
    self._VerifyTwoCallStacksEqual(
        callstack_filters.KeepTopNFrames(top_n)(
            CallStackBuffer(0, frame_list=frame_list)),
        CallStackBuffer(0, frame_list=frame_list[:top_n]))

  def testDoNothingIfTopNFramesFieldIsEmpty(self):
    """Tests that if top_n_frames is None, filter does nothing."""
    frame_list = [
        StackFrame(
            0, 'src/', 'normal_func', 'f.cc', 'dummy/src/f.cc', [2]),
        StackFrame(
            1, 'src/', 'func', 'a.cc', 'a.cc', [1]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    self._VerifyTwoCallStacksEqual(
        callstack_filters.KeepTopNFrames()(stack_buffer), stack_buffer)


class RemoveTopNFramesTest(AnalysisTestCase):
  """Tests that ``RemoveTopNFrames`` works as expected."""

  def testRemoveTopNFrames(self):
    """Tests removing the top n frames of a callstack."""
    frame_list = [
        StackFrame(
            0, 'src/', 'normal_func', 'f.cc', 'dummy/src/f.cc', [2]),
        StackFrame(
            1, 'src/', 'func', 'a.cc', 'a.cc', [1]),
    ]

    top_n = 1
    self._VerifyTwoCallStacksEqual(
        callstack_filters.RemoveTopNFrames(top_n)(
            CallStackBuffer(0, frame_list=frame_list)),
        CallStackBuffer(0, frame_list=frame_list[top_n:]))

  def testDoNothingIfTopNFramesFieldIsEmpty(self):
    """Tests that if top_n_frames is None, filter does nothing."""
    frame_list = [
        StackFrame(
            0, 'src/', 'normal_func', 'f.cc', 'dummy/src/f.cc', [2]),
        StackFrame(
            1, 'src/', 'func', 'a.cc', 'a.cc', [1]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    self._VerifyTwoCallStacksEqual(
        callstack_filters.RemoveTopNFrames()(stack_buffer), stack_buffer)


class FilterJavaJreSdkFramesTest(AnalysisTestCase):
  """Tests that ``FilterJavaJreSdkFrames`` works as expected."""

  def testDoNothingForNonJavaStack(self):
    """Tests that the filter does nothing for non-java stack."""
    frame_list = [
        StackFrame(
            0, 'src/', 'normal_func', 'f.cc', 'dummy/src/f.cc', [2])
    ]
    stack_buffer = CallStackBuffer(0, frame_list=frame_list,
                                   language_type=LanguageType.CPP)
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterJavaJreSdkFrames()(stack_buffer), stack_buffer)

  def testFilterJavaJreSdkFramesForJavaStack(self):
    """Tests that filter java JRE/SDK frames for java stack."""
    frame_list = [
        StackFrame(
            0, 'an/', 'javax.f', 'javax/f.java', 'javax/f.java', [2]),
        StackFrame(
            1, 'an/', 'org.omg.a', 'org/omg/a.java', 'org/omg/a.java', [2]),
        StackFrame(0, 'an/', 'an.b', 'an/b.java', 'an/b.java', [12, 13]),
    ]
    stack_buffer = CallStackBuffer(0, frame_list=frame_list,
                                   language_type=LanguageType.JAVA)
    expected_stack_buffer = CallStackBuffer(0, frame_list=frame_list[2:],
                                            language_type=LanguageType.JAVA)

    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterJavaJreSdkFrames()(stack_buffer),
        expected_stack_buffer)


class KeepV8FramesIfV8GeneratedJITCrashTest(AnalysisTestCase):
  """Tests that ``KeepV8FramesIfV8GeneratedJITCrash`` works as expected."""

  def testKeepV8FramesIfV8GeneratedJITCrash(self):
    """Tests that ``KeepV8FramesIfV8GeneratedJITCrash`` keeps v8 frames."""
    frame_list = [
        StackFrame(
            0, 'src/v8', 'v8::internal::Invoke', 'f.cc', 'dummy/src/f.cc', [2]),
        StackFrame(
            1, 'src/v8', 'func', 'a.cc', 'a.cc', [1]),
        StackFrame(
            2, 'src', 'func', 'b.cc', 'b.cc', [2, 3]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list,
                                   metadata={'top_frame_has_no_symbols': True})
    expected_stack_buffer = CallStackBuffer(
        0, frame_list=frame_list[:2],
        metadata={'top_frame_has_no_symbols': True})
    self._VerifyTwoCallStacksEqual(
        callstack_filters.KeepV8FramesIfV8GeneratedJITCrash()(stack_buffer),
        expected_stack_buffer)

  def testDoNothingForNonV8GeneratedJITCrash(self):
    """Tests that filter does nothing for non v8 generated JIT crash."""
    frame_list = [
        StackFrame(
            0, 'src/v8', 'func', 'a.cc', 'a.cc', [1]),
        StackFrame(
            1, 'src', 'func', 'b.cc', 'b.cc', [2, 3]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list,
                                   metadata={'top_frame_has_no_symbols': True})
    self._VerifyTwoCallStacksEqual(
        callstack_filters.KeepV8FramesIfV8GeneratedJITCrash()(stack_buffer),
        stack_buffer)


class FilterV8FramesForV8APIBindingCodeTest(AnalysisTestCase):
  """Tests that ``FilterV8FramesForV8APIBindingCode`` works as expected."""

  def testDoNothingForStackWithLessThanTwoFrames(self):
    """Tests that filter nothing if the stack has less than two frames."""
    frame_list = [
        StackFrame(
            0, 'src/v8', 'func', 'a.cc', 'a.cc', [1]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterV8FramesForV8APIBindingCode()(
            stack_buffer),
        stack_buffer)

  def testFilterV8FramesForV8APIBindingBlinkCode(self):
    """Tests that filter V8 frames from V8 binding blink code."""
    frame_list = [
        StackFrame(
            0, 'src/v8', 'func', 'src/api.h', 'src/api.h', [1]),
        StackFrame(
            1, 'src/', 'func', 'out/Release/gen/blink/bindings/a.cc',
            'out/Release/gen/blink/bindings/a.cc', [1]),
        StackFrame(
            2, 'src', 'func', 'a.cc', 'a.cc', [1]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    expected_stack_buffer = CallStackBuffer(0, frame_list=frame_list[2:])
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterV8FramesForV8APIBindingCode()(stack_buffer),
        expected_stack_buffer)

  def testFilterAllFramesForNullPointerDereference(self):
    """Tests that filtering all frames for null pointer dereference stack."""
    frame_list = [
        StackFrame(
            0, 'src/v8', 'func', 'src/api.h', 'src/api.h', [1]),
        StackFrame(
            2, 'src/v8', 'func', 'a.cc', 'a.cc', [1]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    expected_stack_buffer = CallStackBuffer(0, frame_list=[])
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterV8FramesForV8APIBindingCode('0x0000')(
            stack_buffer),
        expected_stack_buffer)

  def testFilterV8FramesForNullPointerDereference(self):
    """Tests that filtering all v8 frames for null pointer dereference stack."""
    frame_list = [
        StackFrame(
            0, 'src/v8', 'func', 'src/api.h', 'src/api.h', [1]),
        StackFrame(
            2, 'src', 'func', 'a.cc', 'a.cc', [1]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    expected_stack_buffer = CallStackBuffer(0, frame_list=frame_list[1:])
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterV8FramesForV8APIBindingCode('0x0000')(
            stack_buffer),
        expected_stack_buffer)

  def testDoNothingForNonV8APIBindingStack(self):
    """Tests that filter does nothing for non v8 api binding stack."""
    frame_list = [
        StackFrame(
            0, 'src/v8', 'func', 'f.cc', 'f.cc', [1]),
        StackFrame(
            2, 'src', 'func', 'a.cc', 'a.cc', [1]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterV8FramesForV8APIBindingCode()(
            stack_buffer),
        stack_buffer)


class FilterFramesAfterBlinkGeneratedCode(AnalysisTestCase):
  """Tests that ``FilterFramesAfterBlinkGeneratedCode`` works as expected."""

  def testDoNothingIfNoBlinkBindingGeneratedCode(self):
    """Tests that filter does nothing if no blink binding generated code."""
    frame_list = [
        StackFrame(
            0, 'src/v8', 'func', 'a.cc', 'a.cc', [1]),
        StackFrame(
            1, 'src', 'func', 'b.cc', 'b.cc', [2, 3]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterFramesAfterBlinkGeneratedCode()(stack_buffer),
        stack_buffer)

  def testFilterFramesAfterBlinkBindingGeneratedCode(self):
    """Tests that filter does nothing if no blink binding generated code."""
    frame_list = [
        StackFrame(
            0, 'src/v8', 'func', 'a.cc', 'a.cc', [1]),
        StackFrame(
            1, 'src/', 'func', 'out/Release/gen/blink/bindings/a.cc',
            'out/Release/gen/blink/bindings/a.cc', [1]),
        StackFrame(
            2, 'src', 'func', 'b.cc', 'b.cc', [2, 3]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    expected_stack_buffer = CallStackBuffer(0, frame_list=frame_list[:1])
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterFramesAfterBlinkGeneratedCode()(stack_buffer),
        expected_stack_buffer)


class FilterV8FramesIfV8notInTopFramesTest(AnalysisTestCase):
  """Tests that ``FilterV8FramesIfV8NotInTopFrames`` works as expected."""

  def testFilterV8FrameIfV8notInTopFrames(self):
    """Tests filtering all v8 frames when condition met.

    If there is no v8 frame in top n frames, the crash should not be caused by
    v8 cls, filter all the remaining v8 frames in the stack."""
    frame_list = [
        StackFrame(
            0, 'src', 'func', 'a.cc', 'a.cc', [1]),
        StackFrame(
            1, 'src', 'func', 'b.cc', 'b.cc', [1]),
        StackFrame(
            2, 'src', 'func', 'c.cc', 'c.cc', [2, 3]),
        StackFrame(
            3, 'src/v8', 'func', 'd.cc', 'd.cc', [1]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    expected_stack_buffer = CallStackBuffer(0, frame_list=frame_list[:3])
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterV8FramesIfV8NotInTopFrames(2)(stack_buffer),
        expected_stack_buffer)

  def testDoNothingIfV8InTopFrames(self):
    """Tests that filter does nothing if there is v8 frame in top frames."""
    frame_list = [
        StackFrame(
            0, 'src/v8', 'func', 'a.cc', 'a.cc', [1]),
        StackFrame(
            1, 'src', 'func', 'b.cc', 'b.cc', [1]),
        StackFrame(
            2, 'src', 'func', 'c.cc', 'c.cc', [2, 3]),
        StackFrame(
            3, 'src/v8', 'func', 'd.cc', 'd.cc', [1]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterV8FramesIfV8NotInTopFrames(2)(stack_buffer),
        stack_buffer)

  def testDoNothingForEmptyStackBuffer(self):
    """Tests that filter does nothing for empty stack buffer."""
    stack_buffer = CallStackBuffer(0, frame_list=[])
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterV8FramesIfV8NotInTopFrames(2)(stack_buffer),
        stack_buffer)


class FilterFramesBeforeAndInBetweenSignaturePartsTest(AnalysisTestCase):
  """Tests ``FilterFramesBeforeAndInBetweenSignaturePartsTest`` filter."""

  def testDoNothingIfSignatueIsEmpty(self):
    """Tests filter does nothing if the signature is empty."""
    frame_list = [
        StackFrame(
            0, 'src', 'func0', 'a.cc', 'a.cc', [1]),
        StackFrame(
            1, 'src', 'func1', 'b.cc', 'b.cc', [1]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    expected_stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterFramesBeforeAndInBetweenSignatureParts(None)(
            stack_buffer),
        expected_stack_buffer)

  def testDoNothingIfNoMatchBetweenFramesAndSignature(self):
    """Tests filter does nothing if frames and signature do not match."""
    frame_list = [
        StackFrame(
            0, 'src', 'func0', 'a.cc', 'a.cc', [1]),
        StackFrame(
            1, 'src', 'func1', 'b.cc', 'b.cc', [1]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    expected_stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterFramesBeforeAndInBetweenSignatureParts(
            'signature')(stack_buffer),
        expected_stack_buffer)

  def testFilterAllFramesBeforeTheFirstMatchedSignaturePart(self):
    """Tests filtering frames before the first matched signature part."""
    frame_list = [
        StackFrame(
            0, 'src/v8', 'func0', 'a.cc', 'a.cc', [1]),
        StackFrame(
            1, 'src', 'func1', 'b.cc', 'b.cc', [1]),
        StackFrame(
            2, 'src', 'func2', 'c.cc', 'c.cc', [2, 3]),
        StackFrame(
            3, 'src/v8', 'func3', 'd.cc', 'd.cc', [1]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    expected_stack_buffer = CallStackBuffer(0, frame_list=frame_list[2:])
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterFramesBeforeAndInBetweenSignatureParts(
            'dummy\nfunc2\nfunc3\n')(stack_buffer),
        expected_stack_buffer)

  def testFilterFramesInBetweenSignatureParts(self):
    """Tests filtering frames in between signature parts."""
    frame_list = [
        StackFrame(
            0, 'src/v8', 'func0', 'a.cc', 'a.cc', [1]),
        StackFrame(
            1, 'src', 'func1', 'b.cc', 'b.cc', [1]),
        StackFrame(
            2, 'src', 'func2', 'c.cc', 'c.cc', [2, 3]),
        StackFrame(
            3, 'src/v8', 'func3', 'd.cc', 'd.cc', [1]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    expected_stack_buffer = CallStackBuffer(
        0, frame_list=[frame_list[0], frame_list[3]])
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterFramesBeforeAndInBetweenSignatureParts(
            'func0\nfunc3')(stack_buffer),
        expected_stack_buffer)

  def testFilterFramesBothBeforeAndInBetweenSignatureParts(self):
    """Tests filtering frames both before and in between signature parts."""
    frame_list = [
        StackFrame(
            0, 'src/v8', 'func0', 'a.cc', 'a.cc', [1]),
        StackFrame(
            1, 'src', 'func1', 'b.cc', 'b.cc', [1]),
        StackFrame(
            2, 'src', 'func2', 'c.cc', 'c.cc', [2, 3]),
        StackFrame(
            3, 'src/v8', 'func3', 'd.cc', 'd.cc', [1]),
    ]

    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    expected_stack_buffer = CallStackBuffer(
        0, frame_list=[frame_list[1], frame_list[3]])
    self._VerifyTwoCallStacksEqual(
        callstack_filters.FilterFramesBeforeAndInBetweenSignatureParts(
            'func1\nfunc3')(stack_buffer),
        expected_stack_buffer)
