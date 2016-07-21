# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from crash import parse_util
from crash.type_enums import CallStackFormatType

# Used to parse a line into StackFrame of a Callstack.
CALLSTACK_FORMAT_TO_PATTERN = {
    CallStackFormatType.JAVA: re.compile(
        r'at ([A-Za-z0-9$._<>]+)\(\w+(\.java)?:(\d+)\)'),
    CallStackFormatType.SYZYASAN: re.compile(
        r'(CF: )?(.*?)( \(FPO: .*\) )?( \(CONV: .*\) )?\[(.*) @ (\d+)\]'),
    CallStackFormatType.DEFAULT: re.compile(
        r'(.*):(\d+)(:\d+)?$')
}


FRAME_INDEX_PATTERN = re.compile(r'\s*#(\d+)\s.*')


class StackFrame(object):
  """Represents a frame in a stacktrace.

  Attributes:
    index (int): Index shown in the stacktrace if a stackframe line looks like
      this - '#0 ...', else use the index in the callstack list.
    dep_path (str): Path of the dep this frame represents, for example,
      'src/', 'src/v8', 'src/skia'...etc.
    function (str): Function that caused the crash.
    file_path (str): Normalized path of the crashed file, with parts dep_path
      and parts before it stripped, for example, api.cc.
    raw_file_path (str): Normalized original path of the crashed file,
      for example, /b/build/slave/mac64/build/src/v8/src/heap/
      incremental-marking-job.cc.
    crashed_line_numbers (list): Line numbers of the file that caused the crash.
    repo_url (str): Repo url of this frame.
  """
  def __init__(self, index, dep_path, function,
               file_path, raw_file_path, crashed_line_numbers,
               repo_url=None):
    self.index = index
    self.dep_path = dep_path
    self.function = function
    self.file_path = file_path
    self.raw_file_path = raw_file_path
    self.crashed_line_numbers = crashed_line_numbers
    self.repo_url = repo_url

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


class CallStack(list):
  """Represents a call stack within a stacktrace. A list of StackFrame objects.

  Attributes:
    priority (int): The smaller the number, the higher the priority beginning
      with 0.
    format_type (CallStackFormatType): Represents the type of line format
      within a callstack. For example:

      CallStackFormatType.JAVA -
      'at com.android.commands.am.Am.onRun(Am.java:353)'

      CallStackFormatType.SYZYASAN -
      'chrome_child!v8::internal::ApplyTransition+0x93 [v8/src/lookup.cc @ 340]'

      CallStackFormatType.DEFAULT -
      '#0 0x32b5982 in get third_party/WebKit/Source/wtf/RefPtr.h:61:43'
    language_type (CallStackLanguageType): Either CPP or JAVA language.
  """
  def __init__(self, priority, format_type=CallStackFormatType.DEFAULT,
               frame_list=None):
    super(CallStack, self).__init__(frame_list or [])

    self.priority = priority
    self.format_type = format_type
    self.language_type = parse_util.GetLanguageTypeFromFormatType(format_type)

  def ParseLine(self, line, deps):
    """Parse line into StackFrame instance and append it if successfully
    parsed."""
    line = line.strip()
    line_pattern = CALLSTACK_FORMAT_TO_PATTERN[self.format_type]

    if self.format_type == CallStackFormatType.JAVA:
      match = line_pattern.match(line)
      if not match:
        return

      function = match.group(1)
      raw_file_path = parse_util.GetFullPathForJavaFrame(function)
      crashed_line_numbers = [int(match.group(3))]

    elif self.format_type == CallStackFormatType.SYZYASAN:
      match = line_pattern.match(line)
      if not match:
        return

      function = match.group(2).strip()
      raw_file_path = match.group(5)
      crashed_line_numbers = [int(match.group(6))]

    else:
      line_parts = line.split()
      if not line_parts or not line_parts[0].startswith('#'):
        return

      match = line_pattern.match(line_parts[-1])
      if not match:
        return

      function = ' '.join(line_parts[3:-1])
      raw_file_path = match.group(1)
      crashed_line_numbers = parse_util.GetCrashedLineRange(
          match.group(2) + (match.group(3) if match.group(3) else ''))

    # Normalize the file path so that it can be compared to repository path.
    dep_path, file_path, repo_url = parse_util.GetDepPathAndNormalizedFilePath(
        raw_file_path, deps)

    # If we have the common stack frame index pattern, then use it
    # since it is more reliable.
    index_match = FRAME_INDEX_PATTERN.match(line)
    if index_match:
      stack_frame_index = int(index_match.group(1))
    else:
      stack_frame_index = len(self)

    self.append(StackFrame(stack_frame_index, dep_path, function, file_path,
                           raw_file_path, crashed_line_numbers, repo_url))
