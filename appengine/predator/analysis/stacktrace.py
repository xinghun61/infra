# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
import math
import re

from analysis import parse_util
from analysis.constants import CHROMIUM_ROOT_PATH
from analysis.constants import CHROMIUM_REPO_URL
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


def _BlameUrl(stackframe, revision):
  """The URL to the git blame of this stackframe's file."""
  if not stackframe.repo_url or not stackframe.dep_path:
    return None

  return '%s/+blame/%s/%s' % (stackframe.repo_url, revision,
                              stackframe.file_path)


class FunctionLine(namedtuple('FunctionLine', ['line', 'sample_fraction'])):
  """Execution data collected by a profiler about a line in a function.

  Represents a line in a function where execution is occurring or the next
  function in the stack is invoked.
  Attributes:
    line (int): The line number.
    sample_fraction (float): The fraction of stacks in the profiler sample where
      that line is executed. Number from 0 to 1.
  """
  pass


class ProfilerStackFrame(namedtuple('ProfilerStackFrame',
    ['index', 'difference', 'log_change_factor', 'responsible', 'dep_path',
     'function', 'file_path', 'raw_file_path', 'repo_url',
     'function_start_line', 'lines_old', 'lines_new'])):
  """Represents a frame in a stacktrace produced by a performance profiler.

  Represents the difference in performance for a given stack frame between one
  version of the code and another.

  Attributes:
    index (int): The depth of this frame in the call tree.
    difference (float): Execution time difference in seconds. Will be positive
      for regressions, negative for improvements.
    log_change_factor (float): The log of the relative change factor of the
      execution time (>0 for regressions, <0 for improvements). The relative
      change factor is the ratio of the function's execution time in the new
      release to its execution time in the old release. This will be Infinity if
      the execution time in the old release is 0 and -Infinity if the execution
      time of the new release is 0.
    responsible (bool): Whether this node is responsible for the difference.
    dep_path (str): Path of the dep this frame represents, for example,
      'src/', 'src/v8', 'src/skia'...etc.

    # The remaining fields will be absent from frames with no symbol information
    # and will default to None.

    function (str): The name of the function in this frame.
    file_path (str): Normalized path of the file, with parts dep_path and parts
      before it stripped, for example, api.cc.
    raw_file_path (str): Original path of the file, normalized to start from the
      root of the Chromium repository, for example,
      src/v8/src/heap/incremental-marking-job.cc.
    repo_url (str): Repo url of this frame.
    function_start_line (int): The line number for the first line of the
      function.
    lines_old (tuple of FunctionLines): Lines in this function where execution
      is occurring or the next function in the stack is invoked, along with the
      fraction of samples distributed between them (recorded in the old version
      of the code). E.g.:
        (FunctionLine(line=490, sample_fraction=0.9),
         FunctionLine(line=511, sample_fraction=0.1))
    lines_new (tuple of FunctionLines): Same as ``lines_old``, but
      recorded in the new version of the code.
  """
  __slots__ = ()

  def __new__(cls, index, difference, log_change_factor, responsible,
              dep_path=None, function=None, file_path=None, raw_file_path=None,
              repo_url=None, function_start_line=None, lines_old=None,
              lines_new=None):
    if index is None:
      raise TypeError('The index must be an int')

    lines_old = tuple(lines_old) if lines_old else None
    lines_new = tuple(lines_new) if lines_new else None

    return super(cls, ProfilerStackFrame).__new__(
        cls, int(index), difference, log_change_factor, responsible, dep_path,
        function, file_path, raw_file_path, repo_url, function_start_line,
        lines_old, lines_new)

  def BlameUrl(self, revision):
    return _BlameUrl(self, revision)

  @property
  def crashed_line_numbers(self):
    """Return relevant line numbers for use by the MinDistance feature."""
    line_numbers = []
    # The ``function_start_line`` is most relevant in cases where a function's
    # signature has changed.
    if self.function_start_line is not None:
      line_numbers.append(self.function_start_line)
    # The ``lines_new`` identifies key points in the function where execution is
    # occurring (mostly calls to other functions), so changes in performance are
    # usually related to changes on or near these lines.
    if self.lines_new is not None:
      line_numbers += [l.line for l in self.lines_new]

    return tuple(sorted(line_numbers)) or None

  @staticmethod
  def Parse(frame_dict, index, deps):
    """Convert frame dict into ``ProfilerStackFrame`` object.

    Args:
      frame_dict (dict): Dict representing a stack frame from UMA Sampling
        Profiler.
      index (int): Index (or depth) of the frame in the call stack.
      deps (dict): Map dependency path to its corresponding Dependency.
    Returns: ``ProfilerStackFrame`` object and ``LanguageType`` of the frame.
    """
    difference = frame_dict['difference']
    log_change_factor = frame_dict['log_change_factor']
    responsible = frame_dict['responsible']
    is_java = False
    # the following fields may not be present
    raw_file_path = frame_dict.get('filename')
    if raw_file_path:
      is_java = raw_file_path.endswith('.java')
      dep_path, normalized_file_path, repo_url = (
          parse_util.GetDepPathAndNormalizedFilePath(raw_file_path,
                                                     deps, is_java))
    else:
      dep_path = None
      normalized_file_path = None
      repo_url = None

    function_name = frame_dict.get('function_name')
    function_start_line = frame_dict.get('function_start_line')
    lines = frame_dict.get('lines')
    if lines:
      lines_old = [FunctionLine(line_dict['line'], line_dict['sample_fraction'])
                   for line_dict in lines[0]]
      lines_new = [FunctionLine(line_dict['line'], line_dict['sample_fraction'])
                   for line_dict in lines[1]]
    else:
      lines_old = None
      lines_new = None

    frame_object = ProfilerStackFrame(index, difference, log_change_factor,
                                      responsible, dep_path, function_name,
                                      normalized_file_path, raw_file_path,
                                      repo_url, function_start_line,
                                      lines_old, lines_new)
    language_type = LanguageType.JAVA if is_java else LanguageType.CPP

    return frame_object, language_type


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
    frame_str = '#%d 0xXXX in %s %s' % (self.index, self.function,
                                        self.raw_file_path)
    if self.crashed_line_numbers:
      frame_str += ':%d' % self.crashed_line_numbers[0]

    # For example, if crashed_line_numbers is [61], returns '... f.cc:61',
    # if is [61, 62], returns '... f.cc:61:1'
    if len(self.crashed_line_numbers) > 1:
      frame_str += ':%d' % (len(self.crashed_line_numbers) - 1)

    return frame_str

  def BlameUrl(self, revision):
    blame_url = _BlameUrl(self, revision)
    if self.crashed_line_numbers:
      blame_url += '#%d' % self.crashed_line_numbers[0]
    return blame_url

  def __str__(self):
    return self.ToString()

  # TODO(katesoina): Remove usage of language_type since it can always be
  # derieved or replaced by formate_type.
  @staticmethod
  def Parse(language_type, format_type, line, deps,
            default_stack_frame_index=None,
            root_path=None, root_repo_url=None):
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
    root_path = root_path or CHROMIUM_ROOT_PATH
    root_repo_url = root_repo_url or CHROMIUM_REPO_URL
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
        raw_file_path, deps, language_type == LanguageType.JAVA,
        root_path=root_path, root_repo_url=root_repo_url)

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

  def ToString(self):  # pragma: no cover
    return ('CRASHED [ERROR @ 0xXXX]\n' +
            '\n'.join([str(frame) for frame in self.frames]))


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

  def ToString(self):  # pragma: no cover
    return '\n\n'.join([stack.ToString() for stack in self.stacks])


class StacktraceBuffer(object):
  """A Mutable type to simplify constructing ``Stacktrace`` objects.

  The class can be converted to immutable stacktrace using ``ToStacktrace``.
  Note, to make this class fully mutable, it should contain CallStackBuffer
  list instead of CallStack list.
  """
  def __init__(self, stacks=None, filters=None):
    """Initialize StacktraceBuffer instance.

    Args:
      stacks (list of CallStackBuffer): CallStackBuffer objects to
        build stacktrace.
      filters (list of CallStackFilters): List of ``CallStackFilter`` instances,
        which filter frames if necessary.
    """
    self.stacks = stacks or []
    self.filters = filters

  def __nonzero__(self):
    """Returns whether this trace buffer is empty."""
    return bool(self.stacks)
  __bool__ = __nonzero__

  def AddFilteredStack(self, stack_buffer):
    """Filters stack_buffer and add it to stacks if it's not empty."""
    # If the callstack is the initial one (infinite priority) or empty, return
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

    callstacks = []
    crash_stack = None
    for stack_buffer in self.stacks:
      if stack_buffer.metadata.get('is_signature_stack'):
        crash_stack = stack_buffer.ToCallStack()
        callstacks.append(crash_stack)
      else:
        callstacks.append(stack_buffer.ToCallStack())

    if crash_stack is None:
      # If there is no signature callstack, fall back to set crash stack using
      # the first least priority callstack.
      crash_stack = min(callstacks, key=lambda stack: stack.priority)

    return Stacktrace(tuple(callstacks), crash_stack)
