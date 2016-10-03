# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from crash.callstack_filters import FilterInlineFunctionFrames
from crash.stacktrace import CallStack
from crash.stacktrace import Stacktrace
from crash.stacktrace_parser import StacktraceParser
from crash.type_enums import CallStackFormatType
from crash.type_enums import CallStackLanguageType


FRACAS_CALLSTACK_START_PATTERN = re.compile(r'CRASHED \[(.*) @ 0x(.*)\]')
JAVA_CALLSTACK_START_PATTERN = re.compile(r'\(JAVA\) CRASHED \[(.*) @ 0x(.*)\]')


class ChromeCrashParser(StacktraceParser):

  def Parse(self, stacktrace_string, deps, signature=None):
    """Parse fracas stacktrace string into Stacktrace instance."""
    stacktrace = Stacktrace()
    # TODO(http://crbug.com/644441): testing against infinity is confusing.
    callstack = CallStack(float('inf'))

    for line in stacktrace_string.splitlines():
      is_new_callstack, stack_priority, format_type, language_type = (
          self._IsStartOfNewCallStack(line))

      if is_new_callstack:
        # If the callstack is not the initial one or empty, add it
        # to stacktrace.
        if callstack.priority != float('inf') and callstack:
          stacktrace.append(callstack)

        callstack = CallStack(stack_priority, format_type, language_type)
      else:
        callstack.ParseLine(line, deps)

    if callstack.priority != float('inf') and callstack:
      stacktrace.append(callstack)

    # Filter all the frames before signature frame.
    if stacktrace:
      stacktrace = Stacktrace(map(FilterInlineFunctionFrames, stacktrace))

    return stacktrace

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
