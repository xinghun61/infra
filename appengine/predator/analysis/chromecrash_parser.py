# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math
import re

from analysis import callstack_detectors
from analysis.callstack_filters import (
    FilterFramesBeforeAndInBetweenSignatureParts)
from analysis.callstack_filters import FilterInlineFunction
from analysis.callstack_filters import KeepTopNFrames
from analysis.stacktrace import CallStackBuffer
from analysis.stacktrace import StacktraceBuffer
from analysis.stacktrace import StackFrame
from analysis.stacktrace import Stacktrace
from analysis.type_enums import CallStackFormatType
from analysis.type_enums import LanguageType

DEFAULT_TOP_N_FRAMES = 7


class FracasCrashParser(object):

  def Parse(self, stacktrace_string, deps, signature=None, top_n_frames=None):
    """Parse fracas stacktrace string into Stacktrace instance."""
    # Filters to filter callstack buffers.
    filters = [FilterFramesBeforeAndInBetweenSignatureParts(signature),
               FilterInlineFunction(),
               KeepTopNFrames(top_n_frames or DEFAULT_TOP_N_FRAMES)]
    stacktrace_buffer = StacktraceBuffer(filters=filters)

    stack_detector = callstack_detectors.ChromeCrashStackDetector()
    # Initial background callstack which is not to be added into Stacktrace.
    stack_buffer = CallStackBuffer()
    for line in stacktrace_string.splitlines():
      start_of_callstack = stack_detector(line)

      if start_of_callstack:
        stacktrace_buffer.AddFilteredStack(stack_buffer)
        stack_buffer = CallStackBuffer.FromStartOfCallStack(start_of_callstack)
      else:
        frame = StackFrame.Parse(stack_buffer.language_type,
                                 stack_buffer.format_type, line, deps,
                                 len(stack_buffer.frames))
        if frame is not None:
          stack_buffer.frames.append(frame)

    # Add the last stack to stacktrace.
    stacktrace_buffer.AddFilteredStack(stack_buffer)
    return stacktrace_buffer.ToStacktrace()


class CracasCrashParser(object):

  def __init__(self):
    self._sub_parser = FracasCrashParser()

  def Parse(self, stacktrace_list, deps, signature=None, top_n_frames=None):
    """Parses a list of stacktrace strings.

    Note that Cracas sends stacktrace strings from different reports, if they
    are different, every single stacktrace has the same format as Fracas
    stacktrace string. So we can use FracasCrashParser as sub parser to parse
    each string in the list.
    """
    callstacks = []
    for stacktrace_str in stacktrace_list:
      sub_stacktrace = self._sub_parser.Parse(stacktrace_str, deps,
                                              signature=signature,
                                              top_n_frames=top_n_frames)
      if sub_stacktrace:
        callstacks.extend(sub_stacktrace.stacks)

    return Stacktrace(callstacks, callstacks[0]) if callstacks else None
