# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math
import re

from crash import callstack_filters
from crash.stacktrace import CallStackBuffer
from crash.stacktrace import StacktraceBuffer
from crash.stacktrace import StackFrame
from crash.stacktrace import Stacktrace
from crash.stacktrace_parser import StacktraceParser
from crash.type_enums import CallStackFormatType
from crash.type_enums import LanguageType

FRACAS_CALLSTACK_START_PATTERN = re.compile(r'CRASHED \[(.*) @ 0x(.*)\]')
JAVA_CALLSTACK_START_PATTERN = re.compile(r'\(JAVA\) CRASHED \[(.*) @ 0x(.*)\]')
DEFAULT_TOP_N_FRAMES = 7


class ChromeCrashParser(StacktraceParser):

  def Parse(self, stacktrace_string, deps, signature=None, top_n_frames=None):
    """Parse fracas stacktrace string into Stacktrace instance."""
    stacktrace_buffer = StacktraceBuffer(signature=signature)
    # Filters to filter callstack buffers.
    filters = [callstack_filters.FilterInlineFunction(),
               callstack_filters.KeepTopNFrames(top_n_frames or
                                                DEFAULT_TOP_N_FRAMES)]

    # Initial background callstack which is not to be added into Stacktrace.
    stack_buffer = CallStackBuffer()
    for line in stacktrace_string.splitlines():
      is_new_callstack, priority, format_type, language_type = (
          self._IsStartOfNewCallStack(line))

      if is_new_callstack:
        # TODO(katesonia): Refactor this logic to ``AddFilteredStack`` method
        # of StacktraceBuffer.
        stack_buffer = StacktraceParser.FilterStackBuffer(stack_buffer, filters)
        if stack_buffer:
          stacktrace_buffer.stacks.append(stack_buffer)

        stack_buffer = CallStackBuffer(priority=priority,
                                       format_type=format_type,
                                       language_type=language_type)
      else:
        frame = StackFrame.Parse(stack_buffer.language_type,
                                 stack_buffer.format_type, line, deps,
                                 len(stack_buffer.frames))
        if frame is not None:
          stack_buffer.frames.append(frame)

    stack_buffer = StacktraceParser.FilterStackBuffer(stack_buffer, filters)
    if stack_buffer:
      stacktrace_buffer.stacks.append(stack_buffer)

    return stacktrace_buffer.ToStacktrace()

  def _IsStartOfNewCallStack(self, line):
    """Determine whether a line is a start of a callstack or not.

    Returns a tuple - (is_new_callstack, stack_priority, format_type,
    language type).
    """
    if FRACAS_CALLSTACK_START_PATTERN.match(line):
      #Fracas only provide magic signature stack (crash stack).
      return True, 0, CallStackFormatType.DEFAULT, LanguageType.CPP

    if JAVA_CALLSTACK_START_PATTERN.match(line):
      return True, 0, CallStackFormatType.DEFAULT, LanguageType.JAVA

    return False, None, None, None
