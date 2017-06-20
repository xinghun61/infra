# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.stacktrace import CallStackBuffer
from analysis.stacktrace import ProfilerStackFrame
from analysis.stacktrace import StacktraceBuffer


class UMASamplingProfilerParser(object):

  def Parse(self, stacks, deps):
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
      deps (dict): Map dependency path to its corresponding Dependency.

    Returns:
      ``Stacktrace`` object or ``None`` if the stacktrace is empty.
    """
    stacktrace_buffer = StacktraceBuffer()
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
