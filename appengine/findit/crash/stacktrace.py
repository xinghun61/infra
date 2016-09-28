# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

# TODO(wrengr): it would be clearer if this file and callstack.py were
# combined into a single file defining all three classes (StackFrame,
# CallStack, StackTrace)

# TODO(http://crbug.com/644476): this class needs a better name.
class Stacktrace(list):
  """A collection of callstacks which together provide a trace of what happened.

  For instance, when doing memory debugging we will have callstacks for
  (1) when the crash occurred, (2) when the object causing the crash
  was allocated, (3) when the object causing the crash was freed (for
  use-after-free crashes), etc. What callstacks are included in the
  trace is unspecified, since this differs for different tools."""
  def __init__(self, stack_list=None, signature=None):
    super(Stacktrace, self).__init__(stack_list or [])

    self._crash_stack = None
    self._signature_parts = None
    if signature:
      # Filter out the types of signature, for example [Out of Memory].
      signature = re.sub('[[][^]]*[]]\s*', '', signature)
      # For clusterfuzz crash, the signature is crash state. It is
      # usually the top 3 important stack frames separated by '\n'.
      self._signature_parts = signature.split('\n')


  @property
  def crash_stack(self):
    """Get the callstack with the highest priority (i.e., whose priority
    field is numerically the smallest) in the stacktrace."""
    if not self:
      logging.warning('Cannot get crash stack for empty stacktrace: %s', self)
      return None

    if self._crash_stack is None and self._signature_parts:
      def _IsSignatureCallstack(callstack):
        for index, frame in enumerate(callstack):
          for signature_part in self._signature_parts:
            if signature_part in frame.function:
              return True, index

        return False, 0

      # Set the crash stack using signature callstack.
      for callstack in self:
        is_signature_callstack, index = _IsSignatureCallstack(callstack)
        if is_signature_callstack:
          # Filter all the stack frames before signature.
          callstack[:] = callstack[index:]
          self._crash_stack = callstack
          break

    # If there is no signature callstack, fall back to set crash stack using
    # the first least priority callstack.
    if self._crash_stack is None:
      self._crash_stack = sorted(self, key=lambda stack: stack.priority)[0]

    return self._crash_stack
