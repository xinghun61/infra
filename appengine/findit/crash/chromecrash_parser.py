# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math
import re

from crash import callstack_detectors
from crash import callstack_filters
from crash.stacktrace import CallStackBuffer
from crash.stacktrace import StacktraceBuffer
from crash.stacktrace import StackFrame
from crash.stacktrace import Stacktrace
from crash.stacktrace_parser import StacktraceParser
from crash.type_enums import CallStackFormatType
from crash.type_enums import LanguageType

DEFAULT_TOP_N_FRAMES = 7


class ChromeCrashParser(StacktraceParser):

  def Parse(self, stacktrace_string, deps, signature=None, top_n_frames=None):
    """Parse fracas stacktrace string into Stacktrace instance."""
    # Filters to filter callstack buffers.
    filters = [callstack_filters.FilterInlineFunction(),
               callstack_filters.KeepTopNFrames(top_n_frames or
                                                DEFAULT_TOP_N_FRAMES)]
    stacktrace_buffer = StacktraceBuffer(signature=signature, filters=filters)

    stack_detector = callstack_detectors.ChromeCrashStackDetector()
    # Initial background callstack which is not to be added into Stacktrace.
    stack_buffer = CallStackBuffer()
    for line in stacktrace_string.splitlines():
      is_new_callstack, priority, format_type, language_type, metadata = (
          stack_detector.IsStartOfNewCallStack(line))

      if is_new_callstack:
        stacktrace_buffer.AddFilteredStack(stack_buffer)
        stack_buffer = CallStackBuffer(priority=priority,
                                       format_type=format_type,
                                       language_type=language_type,
                                       metadata=metadata)
      else:
        frame = StackFrame.Parse(stack_buffer.language_type,
                                 stack_buffer.format_type, line, deps,
                                 len(stack_buffer.frames))
        if frame is not None:
          stack_buffer.frames.append(frame)

    # Add the last stack to stacktrace.
    stacktrace_buffer.AddFilteredStack(stack_buffer)
    return stacktrace_buffer.ToStacktrace()
