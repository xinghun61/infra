# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash.callstack_detectors import StartOfCallStack
from crash.stacktrace import CallStack
from crash.stacktrace import CallStackBuffer
from crash.stacktrace import StackFrame
from crash.stacktrace import Stacktrace
from crash.stacktrace import StacktraceBuffer
from crash.test.stacktrace_test_suite import StacktraceTestSuite
from crash.type_enums import CallStackFormatType
from crash.type_enums import LanguageType
from libs.deps.dependency import Dependency


class CallStackTest(StacktraceTestSuite):

  def testCallStackBool(self):
    self.assertFalse(CallStack(0, [], None, None))
    frame = StackFrame(0, 'src/', 'func', 'f.cc', 'src/f.cc', [])
    self.assertTrue(CallStack(0, [frame], None, None))

  def testStackFrameToString(self):
    self.assertEqual(
        StackFrame(0, 'src/', 'func', 'f.cc', 'src/f.cc', []).ToString(),
        '#0 in func @ f.cc')
    self.assertEqual(
        StackFrame(0, 'src/', 'func', 'f.cc', 'src/f.cc', [1]).ToString(),
        '#0 in func @ f.cc:1')
    self.assertEqual(
        StackFrame(0, 'src/', 'func', 'f.cc', 'src/f.cc', [1, 2]).ToString(),
        '#0 in func @ f.cc:1:1')

  def testBlameUrlForStackFrame(self):
    frame = StackFrame(0, 'src/', 'func', 'f.cc', 'src/f.cc', [])
    self.assertEqual(frame.BlameUrl('1'), None)

    frame = frame._replace(repo_url = 'https://repo_url')
    self.assertEqual(frame.BlameUrl('1'), 'https://repo_url/+blame/1/f.cc')

    frame = frame._replace(crashed_line_numbers = [9, 10])
    self.assertEqual(frame.BlameUrl('1'), 'https://repo_url/+blame/1/f.cc#9')

  def testCallStackConstructorIsLanguageJavaIfFormatJava(self):
    self.assertEqual(
        CallStack(0, format_type=CallStackFormatType.JAVA).language_type,
        LanguageType.JAVA)

  def testParseStackFrameForJavaCallstackFormat(self):
    language_type = None
    format_type = CallStackFormatType.JAVA
    self.assertIsNone(
        StackFrame.Parse(language_type, format_type, 'dummy line', {}))

    deps = {'org/': Dependency('org/', 'https://repo', '1')}
    frame = StackFrame.Parse(language_type, format_type,
        '  at org.a.b(a.java:609)', deps)
    self._VerifyTwoStackFramesEqual(
        frame,
        StackFrame(0, 'org/', 'org.a.b', 'a.java', 'org/a.java', [609]))

  def testParseStackFrameForSyzyasanCallstackFormat(self):
    language_type = None
    format_type = CallStackFormatType.SYZYASAN
    self.assertIsNone(
        StackFrame.Parse(language_type, format_type, 'dummy line', {}))

    deps = {'src/content/': Dependency('src/content/', 'https://repo', '1')}
    frame = StackFrame.Parse(language_type, format_type,
        'c::p::n [src/content/e.cc @ 165]', deps)
    self._VerifyTwoStackFramesEqual(
        frame,
        StackFrame(
            0, 'src/content/', 'c::p::n', 'e.cc', 'src/content/e.cc', [165]))

  def testParseStackFrameForDefaultCallstackFormat(self):
    language_type = None
    format_type = CallStackFormatType.DEFAULT
    self.assertIsNone(
        StackFrame.Parse(language_type, format_type, 'dummy line', {}))

    deps = {'tp/webrtc/': Dependency('tp/webrtc/', 'https://repo', '1')}
    frame = StackFrame.Parse(language_type, format_type,
        '#0 0x52617a in func0 tp/webrtc/a.c:38:3', deps)
    self._VerifyTwoStackFramesEqual(
        frame,
        StackFrame(
            0, 'tp/webrtc/', 'func0', 'a.c', 'tp/webrtc/a.c', [38, 39, 40, 41]))

    frame = StackFrame.Parse(language_type, format_type,
        '#1 0x526 in func::func2::func3 tp/webrtc/a.c:3:2', deps)
    self._VerifyTwoStackFramesEqual(
        frame,
        StackFrame(
            1, 'tp/webrtc/', 'func::func2::func3', 'a.c', 'tp/webrtc/a.c',
            [3, 4, 5]))

  def testParseStackFrameForFracasJavaStack(self):
    format_type = CallStackFormatType.DEFAULT
    language_type = LanguageType.JAVA

    frame = StackFrame.Parse(language_type, format_type,
        '#0 0xxx in android.app.func app.java:2450', {})
    self._VerifyTwoStackFramesEqual(
        frame,
        StackFrame(
            0, '', 'android.app.func', 'android/app.java',
            'android/app.java', [2450]))


class CallStackBufferTest(StacktraceTestSuite):

  def setUp(self):
    super(CallStackBufferTest, self).setUp()
    self.stack_buffer = CallStackBuffer(0, frame_list=[
        StackFrame(0, 'repo/path1', 'func1', 'a/c/f1.cc', 'a/b/f1.cc',
                   [1, 2], 'https://repo1'),
        StackFrame(1, 'repo/path2', 'func2', 'a/c/f2.cc', 'a/b/f2.cc',
                   [11, 12, 13], 'https://repo2')])

  def testCallStackBufferLen(self):
    """Tests ``len(CallStackBuffer)`` works as expected."""
    self.assertEqual(len(self.stack_buffer), 2)

  def testCallStackBufferBool(self):
    """Tests ``bool`` for ``CallStackBuffer`` object works as expected."""
    self.assertTrue(bool(self.stack_buffer))
    self.assertFalse(bool(CallStackBuffer(0, frame_list=[])))

  def testCallStackBufferIter(self):
    """Tests ``iter`` for ``CallStackBuffer`` works as expected."""
    for index, frame in enumerate(self.stack_buffer.frames):
      self.assertEqual(index, frame.index)

  def testToCallStackForNonEmptyCallStackBuffer(self):
    """Tests ``ToCallStack`` for non empty  ``CallStackBuffer`` object."""
    frame_list=[StackFrame(0, 'repo/path', 'func', 'a/c.cc', 'a/c.cc',
                           [3, 4], 'https://repo')]
    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    expected_callstack = CallStack(stack_buffer.priority,
                                   tuple(frame_list),
                                   CallStackFormatType.DEFAULT,
                                   LanguageType.CPP)
    self.assertTupleEqual(stack_buffer.ToCallStack(), expected_callstack)

  def testToCallStackForEmptyCallStackBuffer(self):
    """Tests ``ToCallStack`` for empty  ``CallStackBuffer`` object."""
    self.assertIsNone(CallStackBuffer(0, frame_list=[]).ToCallStack())

  def testFromNoneStartOfCallStack(self):
    """Tests ``FromStartOfCallStack`` with None input."""
    self.assertIsNone(CallStackBuffer.FromStartOfCallStack(None))

  def testFromStartOfCallStack(self):
    """Tests ``FromStartOfCallStack`` with ``StartOfCallStack`` input."""
    start_of_callstack = StartOfCallStack(0, CallStackFormatType.DEFAULT,
                                          LanguageType.CPP, {'pid': 123})
    stack_buffer = CallStackBuffer.FromStartOfCallStack(start_of_callstack)
    self.assertEqual(stack_buffer.priority, start_of_callstack.priority)
    self.assertEqual(stack_buffer.format_type, start_of_callstack.format_type)
    self.assertEqual(stack_buffer.language_type,
                     start_of_callstack.language_type)
    self.assertDictEqual(stack_buffer.metadata, start_of_callstack.metadata)


class StacktraceTest(StacktraceTestSuite):

  def testStacktraceLen(self):
    """Tests ``len`` for ``Stacktrace`` object."""
    frame_list1 = [
        StackFrame(0, 'src/', 'func', 'file0.cc', 'src/file0.cc', [32])]

    frame_list2 = [
        StackFrame(0, 'src/', 'func2', 'file0.cc', 'src/file0.cc', [32])]

    stack1 = CallStack(0, frame_list1, None, None)
    stack2 = CallStack(1, frame_list2, None, None)
    stacktrace = Stacktrace((stack1, stack2), stack1)
    self.assertEqual(len(stacktrace), 2)

  def testStacktraceBool(self):
    """Tests ``bool`` for ``Stacktrace`` object."""
    self.assertFalse(bool(Stacktrace([], None)))

    frame_list1 = [
        StackFrame(0, 'src/', 'func', 'file0.cc', 'src/file0.cc', [32])]
    frame_list2 = [
        StackFrame(0, 'src/', 'func2', 'file0.cc', 'src/file0.cc', [32])]

    stack1 = CallStack(0, frame_list1, None, None)
    stack2 = CallStack(1, frame_list2, None, None)

    self.assertTrue(bool(Stacktrace((stack1, stack2), stack1)))


class StacktraceBufferTest(StacktraceTestSuite):

  def _DummyFilter(self, stack_buffer):  # pragma: no cover
    return stack_buffer

  def testStacktraceBufferWithoutSignature(self):
    """Tests using least priority stack as crash_stack without  signature."""
    frame_list1 = [
        StackFrame(0, 'src/', 'func', 'file0.cc', 'src/file0.cc', [32])]
    frame_list2 = [
        StackFrame(0, 'src/', 'func2', 'file0.cc', 'src/file0.cc', [32])]

    stack1 = CallStackBuffer(0, frame_list=frame_list1)
    stack2 = CallStackBuffer(1, frame_list=frame_list2)
    stacktrace = StacktraceBuffer([stack1, stack2]).ToStacktrace()

    self._VerifyTwoCallStacksEqual(stacktrace.crash_stack, stack1.ToCallStack())

  def testStacktraceBufferWithSignature(self):
    """Tests using stack with signature as crash_stack with signature."""
    frame_list1 = [
        StackFrame(0, 'src/', 'func', 'file0.cc', 'src/file0.cc', [32])]

    frame_list2 = [
        StackFrame(0, 'src/', 'signature_func2', 'f.cc', 'src/f.cc', [32])]

    stack1 = CallStackBuffer(0, frame_list=frame_list1)
    stack2 = CallStackBuffer(1, frame_list=frame_list2)
    stacktrace = StacktraceBuffer([stack1, stack2], 'signature').ToStacktrace()

    self._VerifyTwoCallStacksEqual(stacktrace.crash_stack, stack2.ToCallStack())

  def testAddFitleredStackWithNoFilters(self):
    """Tests that ``AddFilteredStack`` returns None if there is no filters."""
    frame_list = [
        StackFrame(0, 'src/', 'func', 'file0.cc', 'src/file0.cc', [32]),
        StackFrame(0, 'src/', 'func2', 'file0.cc', 'src/file0.cc', [32])]
    stack_buffer = CallStackBuffer(0, frame_list=frame_list)
    stacktrace_buffer = StacktraceBuffer()
    stacktrace_buffer.AddFilteredStack(stack_buffer)
    self.assertEqual(len(stacktrace_buffer.stacks), 1)

  def testFilterInfinityPriorityStackBuffer(self):
    """Tests that ``AddFilteredStack`` returns None for inf priority stack."""
    stack_buffer = CallStackBuffer(priority=float('inf'))
    stacktrace_buffer = StacktraceBuffer(filters=[self._DummyFilter])
    stacktrace_buffer.AddFilteredStack(stack_buffer)
    self.assertEqual(len(stacktrace_buffer.stacks), 0)

  def testFilterEmptyStackBuffer(self):
    """Tests that ``AddFilteredStack`` returns None for empty stack buffer."""
    stack_buffer = CallStackBuffer(frame_list=[])
    stacktrace_buffer = StacktraceBuffer(filters=[self._DummyFilter])
    stacktrace_buffer.AddFilteredStack(stack_buffer)
    self.assertEqual(len(stacktrace_buffer.stacks), 0)

  def testFilterAllFrames(self):
    """Tests that ``AddFilteredStack`` filters all frames and resturns None."""
    frame_list = [
        StackFrame(0, 'src/', 'func', 'file0.cc', 'src/file0.cc', [32]),
        StackFrame(0, 'src/', 'func2', 'file0.cc', 'src/file0.cc', [32])]
    stack_buffer = CallStackBuffer(0, frame_list=frame_list)

    def _MockFilterAllFrames(stack_buffer):
      stack_buffer.frames = None
      return stack_buffer

    stacktrace_buffer = StacktraceBuffer(filters=[_MockFilterAllFrames])
    stacktrace_buffer.AddFilteredStack(stack_buffer)
    self.assertEqual(len(stacktrace_buffer.stacks), 0)

  def testFilterSomeFrames(self):
    """Tests that ``AddFilteredStack`` filters some frames."""
    frame_list = [
        StackFrame(0, 'src/', 'func', 'file0.cc', 'src/file0.cc', [32]),
        StackFrame(0, 'src/', 'func2', 'file0.cc', 'src/file0.cc', [32])]
    stack_buffer = CallStackBuffer(0, frame_list=frame_list)

    def _MockKeepFirstFrame(stack):
      stack.frames = stack.frames[:1]
      return stack

    stacktrace_buffer = StacktraceBuffer(filters=[_MockKeepFirstFrame])
    stacktrace_buffer.AddFilteredStack(stack_buffer)
    self._VerifyTwoCallStacksEqual(
        stacktrace_buffer.stacks[0],
        CallStackBuffer(stack_buffer.priority, frame_list=frame_list[:1]))

  def testEmptyStacktraceBufferToStacktrace(self):
    """Tests that ``ToStacktrace`` returns None for empty stacktrace buffer."""
    self.assertIsNone(StacktraceBuffer([]).ToStacktrace())
