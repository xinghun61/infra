# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from analysis.stacktrace import CallStack
from analysis.type_enums import LanguageType

_INLINE_FUNCTION_FILE_PATH_MARKERS = [
    'third_party/llvm-build/Release+Asserts/include/c++/v1/',
    'linux/debian_wheezy_amd64-sysroot/usr/include/c++/4.6/bits/',
    'eglibc-3GlaMS/eglibc-2.19/sysdeps/unix/',
]

# When checking the null pointer dereference, any dereference of an address
# within the threshold is considered as null pointer dereference. Be consistent
# with the threshold used in Clusterfuzz.
NULL_POINTER_DEREFERENCE_THRESHOLD = 4096
V8_JIT_CODE_MARKER = 'v8::internal::Invoke'
V8_API_H_FILE_PATH = 'src/api.h'
V8_API_CC_FILE_PATH = 'src/api.cc'
V8_DEP_PATH_MARKER = 'src/v8'
BLINK_BINDINGS_GENERATED_PATH_REGEX = re.compile(
    r'out/[^/]+/gen/blink/bindings/.*')
JAVA_JRE_SDK_REGEX = re.compile(
    r'(java\..*|javax\..*|org\.xml\..*|org\.w3c\..*|'
    r'org\.omg\..*|org\.ietf\.jgss\..*)')


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


class KeepTopNFrames(CallStackFilter):
  """Keeps top n frames of a ``CallStackBuffer`` instance."""

  def __init__(self, top_n_frames=None):
    """
    Args:
      top_n_frames (int): the number of top frames to keep.
    """
    self.top_n_frames = top_n_frames

  def __call__(self, stack_buffer):
    """Returns stack_buffer with only top n frames.

    If no self.top_n_frames is None, don't do any filtering.
    """
    if self.top_n_frames is None:
      return stack_buffer

    stack_buffer.frames = stack_buffer.frames[:self.top_n_frames]
    return stack_buffer


class RemoveTopNFrames(CallStackFilter):
  """Removes top n frames of a ``CallStackBuffer`` instance."""

  def __init__(self, top_n_frames=None):
    """
    Args:
      top_n_frames (int): the number of top frames to remove.
    """
    self.top_n_frames = top_n_frames

  def __call__(self, stack_buffer):
    """Returns stack_buffer with top_n_frames removed.

    If self.top_n_frames is None, don't do any filtering.
    """
    if self.top_n_frames is None:
      return stack_buffer

    stack_buffer.frames = stack_buffer.frames[self.top_n_frames:]
    return stack_buffer


class FilterJavaJreSdkFrames(CallStackFilter):
  """Filters out package names from Java JRE/SDK.

  For example: java.*, javax.*, org.xml.*, org.w3c.*, org.omg.*,
  org.ietf.jgss.*. These frames are misleading to Predator.
  """
  def __call__(self, stack_buffer):
    if stack_buffer.language_type != LanguageType.JAVA:
      return stack_buffer

    stack_buffer.frames = filter(
        lambda frame: not JAVA_JRE_SDK_REGEX.match(frame.function),
        stack_buffer.frames)
    return stack_buffer


class KeepV8FramesIfV8GeneratedJITCrash(CallStackFilter):
  """Keeps v8 frames if conditions met.

  If the top-most frames don't have symbols, but the top frame that does is
  ``v8::internal::Invoke``, the bug is likely a crash in
  V8's generated JIT code.
  """
  def __call__(self, stack_buffer):
    if (stack_buffer and V8_JIT_CODE_MARKER in stack_buffer.frames[0].function
        and stack_buffer.metadata.get('top_frame_has_no_symbols')):
      stack_buffer.frames = filter(lambda f: V8_DEP_PATH_MARKER in f.dep_path,
                                   stack_buffer.frames)
    return stack_buffer


class FilterV8FramesForV8APIBindingCode(CallStackFilter):
  """Filters all v8 frames if all conditions met.

  Conditions:
  (1) src/v8/src/api.h or src/v8/src/api.cc appears as the top file in the stack
  trace.
  (2) the second file is not in src/v8/src
  (e.g. src/out/Release/gen/blink/bindings) or the crash is caused by
  dereference of null pointer, then V8 should not be responsible for the crash
  (likely a bindings issue).
  """
  def __init__(self, crash_address=None):
    """
    Args:
      crash_address (str): Address where crash happens.
    """
    # Record the crash address of the to-be-parsed stack_buffer.
    self.crash_address = crash_address

  def __call__(self, stack_buffer):
    if len(stack_buffer.frames) < 2:
      return stack_buffer

    first_frame_is_api_file = (
        V8_DEP_PATH_MARKER in stack_buffer.frames[0].dep_path and
        (V8_API_H_FILE_PATH == stack_buffer.frames[0].file_path or
         V8_API_CC_FILE_PATH == stack_buffer.frames[0].file_path))

    second_frame_not_from_v8_src = (
        V8_DEP_PATH_MARKER not in stack_buffer.frames[1].dep_path or
        not stack_buffer.frames[1].file_path.startswith('src'))

    null_pointer_dereference = False
    if self.crash_address:
      try:
        null_pointer_dereference = int(
            self.crash_address,
            base=16) < NULL_POINTER_DEREFERENCE_THRESHOLD
      except ValueError:  # pragma: no cover
        # some testcases like memcpy-param-overlap have crash addresses like
        # '[0x621000017d00,0x621000018cea) and [0x621000017d16, 0x621000018d00)'
        pass

    if (first_frame_is_api_file and (second_frame_not_from_v8_src or
                                     null_pointer_dereference)):
      stack_buffer.frames = filter(
          lambda f: V8_DEP_PATH_MARKER not in f.dep_path,
          stack_buffer.frames)
      # After deleting all v8 frames, if the top n frames are generated code,
      # need to filter them out.
      top_n_generated_code_frames = 0
      for frame in stack_buffer.frames:
        if not BLINK_BINDINGS_GENERATED_PATH_REGEX.match(frame.file_path):
          break
        top_n_generated_code_frames += 1
      stack_buffer.frames = stack_buffer.frames[top_n_generated_code_frames:]

    return stack_buffer


class FilterFramesAfterBlinkGeneratedCode(CallStackFilter):
  """Filters all the frames after blink generated code."""
  def __call__(self, stack_buffer):
    for index, frame in enumerate(stack_buffer.frames):
      if BLINK_BINDINGS_GENERATED_PATH_REGEX.match(frame.file_path):
        stack_buffer.frames = stack_buffer.frames[:index]
        break

    return stack_buffer


class FilterV8FramesIfV8NotInTopFrames(CallStackFilter):
  """Filters all v8 frames if there is no v8 frames in top_n_frames."""
  def __init__(self, top_n_frames=4):
    self.top_n_frames = top_n_frames

  def __call__(self, stack_buffer):
    need_filter_v8 = False
    for index, frame in enumerate(stack_buffer.frames):
      if index >= self.top_n_frames:
        need_filter_v8 = True
        break

      if V8_DEP_PATH_MARKER in frame.dep_path:
        break

    if not need_filter_v8:
      return stack_buffer

    stack_buffer.frames = filter(
        lambda f: V8_DEP_PATH_MARKER not in f.dep_path, stack_buffer.frames)
    return stack_buffer


# TODO(katesonia):  If the crash state has the information we need, it will
# work. But sometimes it doesn't. For example some Msan jobs.
class FilterFramesBeforeAndInBetweenSignatureParts(CallStackFilter):
  """Filters all frames before and in between signature parts frames.

  Note, for cracas, fracas, the signature is usually one function, however for
  clusterfuzz, the signature is crash_state, which is usually the top 3
  important functions separated by '\n'.
  """
  def __init__(self, signature):
    if signature:
      # Filter out the types of signature, for example [Out of Memory].
      signature = re.sub('[[][^]]*[]]\s*', '', signature)
      # For clusterfuzz crash, the signature is crash state. It is
      # usually the top 3 important stack frames separated by '\n'.
      self.signature_parts = signature.splitlines()
    else:
      self.signature_parts = None

  def __call__(self, stack_buffer):
    if not self.signature_parts:
      return stack_buffer

    def MatchSignatureWithFrames(frames, signature_parts):
      for frame in frames:
        for index, signature_part in enumerate(signature_parts):
          if signature_part in frame.function:
            return True, signature_parts[index:]

      return False, None

    def FilterFrames(frames, signature_parts):
      frame_index = 0
      signature_index = 0
      filtered_index = []
      while (signature_index < len(signature_parts) and
             frame_index < len(frames)):
        frame = frames[frame_index]
        signature_part = signature_parts[signature_index]
        if signature_part in frame.function:
          signature_index += 1
        else:
          filtered_index.append(frame_index)

        frame_index += 1

      return [frame for index, frame in enumerate(frames)
              if not index in filtered_index]

    match, valid_signature_parts = MatchSignatureWithFrames(
        stack_buffer.frames, self.signature_parts)
    if match:
      # Filter all the stack frames before signature.
      stack_buffer.frames = FilterFrames(
          stack_buffer.frames, valid_signature_parts)
      stack_buffer.metadata['is_signature_stack'] = True

    return stack_buffer
