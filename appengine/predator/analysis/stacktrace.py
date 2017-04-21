# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
import copy
import logging
import math
import re

from analysis import parse_util
from analysis.type_enums import CallStackFormatType
from analysis.type_enums import LanguageType

# Used to parse a line into StackFrame of a Callstack.
CALLSTACK_FORMAT_TO_PATTERN = {
    CallStackFormatType.JAVA: re.compile(
        r'at ([A-Za-z0-9$._<>]+)\(\w+(\.java)?:(\d+)\)'),
    CallStackFormatType.SYZYASAN: re.compile(
        r'(CF: )?(.*?)( \(FPO: .*\) )?( \(CONV: .*\) )?\[(.*) @ (\d+)\]'),
    CallStackFormatType.DEFAULT: re.compile(
        r'(.*?):(\d+)(:\d+)?$')
}

FRAME_INDEX_PATTERN = re.compile(r'\s*#(\d+)\s.*')

_DEFAULT_FORMAT_TYPE = CallStackFormatType.DEFAULT


class StackFrame(namedtuple('StackFrame',
    ['index', 'dep_path', 'function', 'file_path', 'raw_file_path',
     'crashed_line_numbers', 'repo_url'])):
  """Represents a frame in a stacktrace.

  Attributes:
    index (int): Index shown in the stacktrace if a stackframe line
      looks like this - '#0 ...', else use the index in the callstack
      list.
    dep_path (str): Path of the dep this frame represents, for example,
      'src/', 'src/v8', 'src/skia'...etc.
    function (str): Function that caused the crash.
    file_path (str): Normalized path of the crashed file, with parts
      dep_path and parts before it stripped, for example, api.cc.
    raw_file_path (str): Normalized original path of the crashed file,
      for example, /b/build/slave/mac64/build/src/v8/src/heap/
      incremental-marking-job.cc.
    crashed_line_numbers (tuple of int): Line numbers of the file that
      caused the crash.
    repo_url (str): Repo url of this frame.
  """
  __slots__ = ()

  def __new__(cls, index, dep_path, function, file_path, raw_file_path,
              crashed_line_numbers, repo_url=None):
    if index is None: # pragma: no cover
      raise TypeError('The index must be an int')
    return super(cls, StackFrame).__new__(
        cls, int(index), dep_path, function, file_path, raw_file_path,
        tuple(crashed_line_numbers), repo_url)

  def ToString(self):
    frame_str = '#%d in %s @ %s' % (self.index, self.function, self.file_path)
    if self.crashed_line_numbers:
      frame_str += ':%d' % self.crashed_line_numbers[0]

    # For example, if crashed_line_numbers is [61], returns '... f.cc:61',
    # if is [61, 62], returns '... f.cc:61:1'
    if len(self.crashed_line_numbers) > 1:
      frame_str += ':%d' % (len(self.crashed_line_numbers) - 1)

    return frame_str

  def BlameUrl(self, revision):
    if not self.repo_url or not self.dep_path:
      return None

    blame_url = '%s/+blame/%s/%s' % (self.repo_url, revision, self.file_path)
    if self.crashed_line_numbers:
      blame_url += '#%d' % self.crashed_line_numbers[0]

    return blame_url

  def __str__(self):
    return self.ToString()

  # TODO(katesoina): Remove usage of language_type since it can always be
  # derieved or replaced by formate_type.
  @staticmethod
  def Parse(language_type, format_type, line, deps,
            default_stack_frame_index=None):
    """Parse line into a StackFrame instance, if possible.

    Args:
      language_type (LanguageType): the language the line is in.
      format_type (CallStackFormatType): the format the line is in.
      line (str): The line to be parsed.
      deps (dict): Map dependency path to its corresponding Dependency.
      default_stack_frame_index (int): The default stack frame index if index
        cannot be parsed from line.

    Returns:
      A ``StackFrame`` or ``None``.
    """
    # TODO(wrengr): how can we avoid duplicating this logic from ``CallStack``?
    format_type = format_type or _DEFAULT_FORMAT_TYPE

    default_language_type = (
        LanguageType.JAVA if format_type == CallStackFormatType.JAVA else
        LanguageType.CPP)
    language_type = language_type or default_language_type

    line = line.strip()
    line_pattern = CALLSTACK_FORMAT_TO_PATTERN[format_type]

    if format_type == CallStackFormatType.JAVA:
      match = line_pattern.match(line)
      if not match:
        return None

      function = match.group(1)
      raw_file_path = parse_util.GetFullPathForJavaFrame(function)
      crashed_line_numbers = [int(match.group(3))]

    elif format_type == CallStackFormatType.SYZYASAN:
      match = line_pattern.match(line)
      if not match:
        return None

      function = match.group(2).strip()
      raw_file_path = match.group(5)
      crashed_line_numbers = [int(match.group(6))]

    else:
      line_parts = line.split()
      if not line_parts or not line_parts[0].startswith('#'):
        return None

      match = line_pattern.match(line_parts[-1])
      if not match: # pragma: no cover
        return None

      function = ' '.join(line_parts[3:-1])

      raw_file_path = match.group(1)
      # Fracas java stack has default format type.
      if language_type == LanguageType.JAVA:
        raw_file_path = parse_util.GetFullPathForJavaFrame(function)

      crashed_line_numbers = parse_util.GetCrashedLineRange(
          match.group(2) + (match.group(3) if match.group(3) else ''))
    # Normalize the file path so that it can be compared to repository path.
    dep_path, file_path, repo_url = parse_util.GetDepPathAndNormalizedFilePath(
        raw_file_path, deps, language_type == LanguageType.JAVA)

    # If we have the common stack frame index pattern, then use it
    # since it is more reliable.
    index_match = FRAME_INDEX_PATTERN.match(line)
    if index_match:
      stack_frame_index = int(index_match.group(1))
    else:
      stack_frame_index = int(default_stack_frame_index or 0)

    return StackFrame(stack_frame_index, dep_path, function, file_path,
                      raw_file_path, crashed_line_numbers, repo_url)


# N.B., because ``list`` is mutable it isn't hashable, thus cannot be
# used as a key in a dict. Because we want to usecallstacks as keys (for
# memoization) we has-a tuple rather than is-a list.
class CallStack(namedtuple('CallStack',
    ['priority', 'frames', 'format_type', 'language_type'])):
  """A stack (sequence of ``StackFrame`` objects)  in a ``Stacktrace``.

  Attributes:
    priority (int): The smaller the number, the higher the priority beginning
      with 0.
    frames (tuple of StackFrame): the frames in order from bottom to top.
    format_type (CallStackFormatType): Represents the type of line format
      within a callstack. For example:

      CallStackFormatType.JAVA -
      'at com.android.commands.am.Am.onRun(Am.java:353)'

      CallStackFormatType.SYZYASAN -
      'chrome_child!v8::internal::ApplyTransition+0x93 [v8/src/lookup.cc @ 340]'

      CallStackFormatType.DEFAULT -
      '#0 0x32b5982 in get third_party/WebKit/Source/wtf/RefPtr.h:61:43'
    language_type (LanguageType): Either CPP or JAVA language.
  """
  __slots__ = ()

  def __new__(cls, priority, frame_list=None,
              format_type=None, language_type=None):
    """Construct a new ``CallStack``.

    N.B., we use ``None`` as the default value of the optional arguments
    so that if callers need to explicitly provide those arguments but
    don't have an explicit value, they can pass ``None`` to get at the
    default without needing to be kept in sync with this constructor. For
    example, the ``ChromeCrashParser.Parse`` constructs a stack and they
    need to keep track of all the arguments to be passed to this function.

    Args:
      frame_list (iterable of StackFrame): Optional. The frames in the stack.
      priority (int): The priority of this stack in its ``Stacktrace``.
      format_type (CallStackFormatType): Optional. The stack's format.
      language_type (CallStackLanguageType): Optional. The stack's language.
    """
    # TODO(katesonia): Move these defaults to CallStackBuffer, since too many
    # tests impact, do this in another cl.
    format_type = format_type or _DEFAULT_FORMAT_TYPE

    default_language_type = (
        LanguageType.JAVA if format_type == CallStackFormatType.JAVA else
        LanguageType.CPP)

    language_type = language_type or default_language_type
    return super(cls, CallStack).__new__(
        cls, priority, tuple(frame_list or []), format_type, language_type)

  def __len__(self):
    """Returns the number of frames in this stack."""
    return len(self.frames)

  def __nonzero__(self):
    """Returns whether this stack is empty."""
    return bool(self.frames)

  __bool__ = __nonzero__


class CallStackBuffer(object):
  """A Mutable type to simplify constructing ``CallStack`` objects.

  The class can be converted to immutable callstack
  using ``ToCallStack``.
  """
  # TODO(http://crbug.com/644441): testing against infinity is confusing.
  def __init__(self, priority=float('inf'), frame_list=None,
               format_type=None, language_type=None, metadata=None):
    self.priority = priority
    self.format_type = format_type
    self.language_type = language_type
    self.frames = frame_list or []
    # metadata is used to keep miscellaneous data that can be used in
    # filitering, commputing priority and so on.
    # this metadata won't be kept in CallStack instance returned by ToCallStack.
    self.metadata = metadata or {}

  def __len__(self):
    """Returns the number of frames in this stack."""
    return len(self.frames)

  def __nonzero__(self):
    """Returns whether this stack is empty."""
    return bool(self.frames)

  __bool__ = __nonzero__

  def ToCallStack(self):
    """Converts ``CallStackBuffer`` object to ``CallStack`` object.

    Note, some metadata will be discarded after the conversion.
    """
    if not self:
      return None

    return CallStack(self.priority, tuple(self.frames),
                     self.format_type, self.language_type)

  @staticmethod
  def FromStartOfCallStack(start_of_callstack):
    """Constructs a ``CallStackBuffer`` from a ``StartOfCallStack``."""
    if not start_of_callstack:
      return None

    return CallStackBuffer(
        priority=start_of_callstack.priority,
        format_type=start_of_callstack.format_type,
        language_type=start_of_callstack.language_type,
        metadata=start_of_callstack.metadata)


# N.B., because ``list`` is mutable it isn't hashable, thus cannot be
# used as a key in a dict. Because we want to usecallstacks as keys (for
# memoization) we has-a tuple rather than is-a list.
# TODO(http://crbug.com/644476): this class needs a better name.
class Stacktrace(namedtuple('Stacktrace', ['stacks', 'crash_stack'])):
  """A collection of callstacks which together provide a trace of what happened.

  For instance, when doing memory debugging we will have callstacks for
  (1) when the crash occurred, (2) when the object causing the crash
  was allocated, (3) when the object causing the crash was freed (for
  use-after-free crashes), etc. What callstacks are included in the
  trace is unspecified, since this differs for different tools."""
  __slots__ = ()
  def __new__(cls, stacks, crash_stack):
    return super(cls, Stacktrace).__new__(cls, tuple(stacks), crash_stack)

  def __len__(self):
    """Returns the number of stacks in this trace."""
    return len(self.stacks)

  def __nonzero__(self):
    """Returns whether this trace is empty."""
    return bool(self.stacks)

  __bool__ = __nonzero__


class StacktraceBuffer(object):
  """A Mutable type to simplify constructing ``Stacktrace`` objects.

  The class can be converted to immutable stacktrace using ``ToStacktrace``.
  Note, to make this class fully mutable, it should contain CallStackBuffer
  list instead of CallStack list.
  """
  def __init__(self, stacks=None, signature=None, filters=None):
    """Initialize StacktraceBuffer instance.

    Args:
      stacks (list of CallStackBuffer): CallStackBuffer objects to
        build stacktrace.
      signature (str): The signature is used to determine the crash stack.
      filters (list of CallStackFilters): List of ``CallStackFilter`` instances,
        which filter frames if necessary.
    """
    self.stacks = stacks or []
    if signature:
      # Filter out the types of signature, for example [Out of Memory].
      signature = re.sub('[[][^]]*[]]\s*', '', signature)
      # For clusterfuzz crash, the signature is crash state. It is
      # usually the top 3 important stack frames separated by '\n'.
      self.signature_parts = signature.splitlines()
    else:
      self.signature_parts = None

    self.filters = filters

  def __nonzero__(self):
    """Returns whether this trace buffer is empty."""
    return bool(self.stacks)
  __bool__ = __nonzero__

  def AddFilteredStack(self, stack_buffer):
    """Filters stack_buffer and add it to stacks if it's not empty."""
    # If the callstack is the initial one (infinte priority) or empty, return
    # None.
    if math.isinf(stack_buffer.priority) or not stack_buffer.frames:
      return

    for stack_filter in self.filters or []:
      stack_buffer = stack_filter(stack_buffer)
      if not stack_buffer:
        return

    self.stacks.append(stack_buffer)

  def ToStacktrace(self):
    """Converts to ``Stacktrace`` object."""
    if not self:
      return None

    # Get the callstack with the highest priority (i.e., whose priority
    # field is numerically the smallest) in the stacktrace.
    crash_stack_index = None
    if self.signature_parts:
      def _IsSignatureCallstack(callstack):
        for index, frame in enumerate(callstack.frames):
          for signature_part in self.signature_parts:
            if signature_part in frame.function:
              return True, index

        return False, 0

      # Set the crash stack using signature callstack.
      for stack_index, stack_buffer in enumerate(
          self.stacks):  # pragma: no cover.
        is_signature_stack, frame_index = _IsSignatureCallstack(stack_buffer)
        if is_signature_stack:
          # Filter all the stack frames before signature.
          stack_buffer.frames = stack_buffer.frames[frame_index:]
          crash_stack_index = stack_index
          break

    # Convert mutable callstack buffers to immutable callstacks.
    callstacks = [stack_buffer.ToCallStack()
                  for stack_buffer in self.stacks]

    if crash_stack_index is None:
      # If there is no signature callstack, fall back to set crash stack using
      # the first least priority callstack.
      crash_stack = min(callstacks, key=lambda stack: stack.priority)
    else:
      crash_stack = callstacks[crash_stack_index]

    return Stacktrace(tuple(callstacks), crash_stack)
