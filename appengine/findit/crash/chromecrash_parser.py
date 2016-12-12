# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math
import re

from crash.callstack_filters import FilterInlineFunctionFrames
from crash.stacktrace import CallStack
from crash.stacktrace import StackFrame
from crash.stacktrace import Stacktrace
from crash.stacktrace_parser import StacktraceParser
from crash.type_enums import CallStackFormatType, CallStackLanguageType


FRACAS_CALLSTACK_START_PATTERN = re.compile(r'CRASHED \[(.*) @ 0x(.*)\]')
JAVA_CALLSTACK_START_PATTERN = re.compile(r'\(JAVA\) CRASHED \[(.*) @ 0x(.*)\]')


class ChromeCrashParser(StacktraceParser):

  def Parse(self, stacktrace_string, deps, signature=None):
    """Parse fracas stacktrace string into Stacktrace instance."""
    callstacks = []
    # TODO(http://crbug.com/644441): testing against infinity is confusing.
    stack_priority = float('inf')
    format_type = None
    language_type = None
    frame_list = []

    for line in stacktrace_string.splitlines():
      is_new_callstack, this_priority, this_format_type, this_language_type = (
          self._IsStartOfNewCallStack(line))

      if is_new_callstack:
        # If the callstack is not the initial one or empty, add it
        # to stacktrace.
        if not math.isinf(stack_priority) and frame_list:
          callstacks.append(CallStack(stack_priority, format_type=format_type,
              language_type=language_type, frame_list=frame_list))

        stack_priority = this_priority
        format_type = this_format_type
        language_type = this_language_type
        frame_list = []
      else:
        frame = StackFrame.Parse(language_type, format_type, line, deps,
            len(frame_list))
        if frame is not None:
          frame_list.append(frame)

    if not math.isinf(stack_priority) and frame_list:
      callstacks.append(CallStack(stack_priority, format_type=format_type,
          language_type=language_type, frame_list=frame_list))

    # Filter all the frames before signature frame.
    return Stacktrace(map(FilterInlineFunctionFrames, callstacks))

  def _IsStartOfNewCallStack(self, line):
    """Determine whether a line is a start of a callstack or not.
    Returns a tuple - (is_new_callstack, stack_priority, format_type,
    language type).
    """
    if FRACAS_CALLSTACK_START_PATTERN.match(line):
      #Fracas only provide magic signature stack (crash stack).
      return True, 0, CallStackFormatType.DEFAULT, CallStackLanguageType.CPP

    if JAVA_CALLSTACK_START_PATTERN.match(line):
      return True, 0, CallStackFormatType.DEFAULT, CallStackLanguageType.JAVA

    return False, None, None, None
