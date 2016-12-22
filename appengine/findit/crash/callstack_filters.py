# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

_INLINE_FUNCTION_FILE_PATH_MARKERS = [
    'third_party/llvm-build/Release+Asserts/include/c++/v1/',
    'linux/debian_wheezy_amd64-sysroot/usr/include/c++/4.6/bits/',
    'eglibc-3GlaMS/eglibc-2.19/sysdeps/unix/',
]


class CallStackFilter(object):
  """Filters frames of a callstack buffer."""

  def __call__(self, stack_buffer):
    """Returns the stack_buffer with frames filtered.

    Args:
      stack_buffer (CallStackBuffer): stack buffer to be filtered.

    Return:
      A new ``CallStackBuffer`` instance.
    """
    raise NotImplementedError()


class FilterInlineFunction(CallStackFilter):
  """Filters all the stack frames for inline function file paths.

  File paths for inline functions are not the oringinal file paths. They
  should be filtered out.

  Returns stack_buffer with all frames with inline function filtered.
  """
  def __call__(self, stack_buffer):
    def _IsNonInlineFunctionFrame(frame):
      for path_marker in _INLINE_FUNCTION_FILE_PATH_MARKERS:
        if path_marker in frame.file_path:
          return False

      return True

    stack_buffer.frames = filter(_IsNonInlineFunctionFrame, stack_buffer.frames)
    return stack_buffer


# TODO(katesonia): Add TopNFramesFilter to replace the SliceFrames in changelist
# classifier.
