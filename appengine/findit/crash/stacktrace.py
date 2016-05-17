# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re


class Stacktrace(list):
  """Interface Represents Stacktrace object.

  Contains a list of callstacks, because one stacktrace may have more than
  one callstacks."""
  def __init__(self, stack_list=None, signature=None):
    super(Stacktrace, self).__init__(stack_list or [])

    if signature:
      # Filter out the types of signature, for example [Out of Memory].
      signature = re.sub('[[][^]]*[]]\s*', '', signature)

    self.signature = signature
    self._crash_stack = None

  @property
  def crash_stack(self):
    """Gets the crash stack with the highest (lowest number) priority in
    stacktrace."""
    if not self:
      logging.warning('Cannot get crash stack for empty stacktrace: %s', self)
      return None

    if self._crash_stack is None and self.signature:
      # For clusterfuzz crash, the signature is crash state, it is usually the
      # top 3 crash functions seperated by '\n'.
      signature_parts = self.signature.split('\n')

      def _IsSignatureCallstack(callstack):
        for index, frame in enumerate(callstack):
          for signature_part in signature_parts:
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
