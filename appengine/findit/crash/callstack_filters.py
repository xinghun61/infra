# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re


def FilterFramesBeforeSignature(callstack, signature):
  """Filter all the stack frames before the signature frame.

  Note: The callstack is filtered in place.
  """
  if not signature:
    return

  signature_frame_index = 0
  # Filter out the types of signature, for example [Out of Memory].
  signature = re.sub('[[][^]]*[]]\s*', '', signature)

  for index, frame in enumerate(callstack):
    if signature in frame.function:
      signature_frame_index = index

  callstack[:] = callstack[signature_frame_index:]
