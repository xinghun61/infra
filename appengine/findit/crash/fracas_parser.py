# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from crash.callstack import CallStack
from crash.stacktrace import Stacktrace
from crash.stacktrace_parser import StacktraceParser
from crash.type_enums import CallStackFormatType


FRACAS_CALLSTACK_START_PATTERN = re.compile(r'CRASHED \[(.*) @ 0x(.*)\]')


_INFINITY_PRIORITY = 1000


class FracasParser(StacktraceParser):

  def Parse(self, stacktrace_string, deps):
    """Parse fracas stacktrace string into Stacktrace instance."""
    stacktrace = Stacktrace()
    callstack = CallStack(_INFINITY_PRIORITY)

    for line in stacktrace_string.splitlines():
      is_new_callstack, stack_priority, format_type = (
          self._IsStartOfNewCallStack(line))

      if is_new_callstack:
        # If the callstack is not the initial one or empty, add it
        # to stacktrace.
        if callstack.priority != _INFINITY_PRIORITY and callstack:
          stacktrace.append(callstack)

        callstack = CallStack(stack_priority, format_type)
      else:
        callstack.ParseLine(line, deps)

    if callstack.priority != _INFINITY_PRIORITY and callstack:
      stacktrace.append(callstack)

    return stacktrace

  def _IsStartOfNewCallStack(self, line):
    """Determine whether a line is a start of a callstack or not.
    Returns a tuple - (is_new_callstack, stack_priority, format_type).
    """
    if FRACAS_CALLSTACK_START_PATTERN.match(line):
      #Fracas only provide magic signature stack (crash stack).
      return True, 0, CallStackFormatType.DEFAULT

    return False, None, None
