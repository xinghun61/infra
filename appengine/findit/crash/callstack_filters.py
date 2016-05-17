# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from crash.callstack import CallStack


_INLINE_FUNCTION_FILE_PATH_MARKERS = [
    'third_party/llvm-build/Release+Asserts/include/c++/v1/',
    'linux/debian_wheezy_amd64-sysroot/usr/include/c++/4.6/bits/',
    'eglibc-3GlaMS/eglibc-2.19/sysdeps/unix/',
]


def FilterInlineFunctionFrames(callstack):
  """Filters all the stack frames with inline function file paths.

  File paths for inline functions are not the oringinal file paths. They
  should be filtered out.
  """
  def _IsNonInlineFunctionFrame(frame):
    for path_marker in _INLINE_FUNCTION_FILE_PATH_MARKERS:
      if path_marker in frame.file_path:
        return False

    return True

  return CallStack(callstack.priority, callstack.format_type,
                   filter(_IsNonInlineFunctionFrame, callstack))
