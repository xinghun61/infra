# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math

from crash.stacktrace import CallStackBuffer
from crash.stacktrace import Stacktrace


class StacktraceParser(object):

  @staticmethod
  def FilterStackBuffer(stack_buffer, filters):
    """Builds stack buffer to keep all the Callstack inforamtion and metadata.

    Filter stack buffers and cache all the metadata for later use in
    ``BuildStackTrace``.

    Args:
      stack_buffer (CallStackBuffer): callstack buffer to be filtered.
      filters (list): List of Filter objs, each Filter obj is callable and takes
        stack_buffer as the only parameter.

    Returns:
      A new ``CallStackBuffer`` instance, None when all the frames of the
      stack buffer are filtered.
    """
    # If the callstack is the initial one (infinte priority) or empty, return
    # None.
    if math.isinf(stack_buffer.priority) or not stack_buffer.frames:
      return None

    for stack_filter in filters:
      stack_buffer = stack_filter(stack_buffer)
      if not stack_buffer:
        return None

    return stack_buffer

  def Parse(self, stacktrace_string, deps, signature=None):
    raise NotImplementedError()

  def _IsStartOfNewCallStack(self, line):
    raise NotImplementedError()
