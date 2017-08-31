# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis import callstack_filters
from analysis.stacktrace import CallStackBuffer
from analysis.stacktrace import ProfilerStackFrame
from analysis.stacktrace import StacktraceBuffer


class UMASamplingProfilerParser(object):

  def Parse(self, stacks, subtree_root_depth, deps):
    """Parse the list of stacks provided by UMA into a ``Stacktrace`` object.

    Args:
      stacks (list): List of dicts representing stacks, e.g.:
      [
        {
          'frames': [
            {
              'difference': 0.0018545067156028328,
              'log_change_factor': -8.1878,
              'responsible': false,
              'filename': 'chrome/app/chrome_exe_main_win.cc',
              'function_name': 'wWinMain',
              'function_start_line': 484,
              'callee_lines': [{'line': 490, 'sample_fraction': 0.9},
                               {'line': 511, 'sample_fraction': 0.1}]
            },
            ...
            ]
        },
        ...
      ]
      subtree_root_depth (int): Depth of the subtree root. Frames above this
        depth will be filtered out so that the ``Stacktrace`` object consists
        only of the subtree.
      deps (dict): Map dependency path to its corresponding Dependency.

    Returns:
      ``Stacktrace`` object or ``None`` if the stacktrace is empty.
    """
    # TODO(wittman): Change the filtering logic to use the ``responsible`` field
    # after old data has been re-generated
    if _IncludeFrameAboveRoot(stacks, subtree_root_depth):
      filter_depth = subtree_root_depth - 1
    else:
      filter_depth = subtree_root_depth

    filters = [callstack_filters.RemoveTopNFrames(filter_depth)]
    stacktrace_buffer = StacktraceBuffer(filters=filters)

    for stack in stacks:
      # TODO(cweakliam) determine how best to calculate priority for a callstack
      # (or if I even need to)
      callstack_buffer = CallStackBuffer(priority=0)
      for index, frame in enumerate(stack['frames']):
        frame_object, language_type = ProfilerStackFrame.Parse(frame, index,
                                                               deps)
        callstack_buffer.frames.append(frame_object)
      if callstack_buffer:
        callstack_buffer.language_type = language_type
        stacktrace_buffer.AddFilteredStack(callstack_buffer)

    return stacktrace_buffer.ToStacktrace()


def _IncludeFrameAboveRoot(stacks, subtree_root_depth):
  """Should the frame above the root of the subtree be included?

  Include the frame if the performance change is a total shift of execution
  at the root (due for example to the root function being added, deleted, or
  renamed). Uses a simple heuristic rule to determine if this is the case.
  """
  if subtree_root_depth == 0:
    return False

  root = stacks[0]['frames'][subtree_root_depth]
  log_change_factor = root['log_change_factor']
  return log_change_factor in (float('inf'), float('-inf'))