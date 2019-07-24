# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utility functions for code coverage."""

_METRIC_NAME_DETAIL_MAPPING = {
    'line': (
        '''Line coverage is the percentage of code lines which have been
           executed at least once. Only executable lines within function bodies
           are considered to be code lines.'''),
    'function': (
        '''Function coverage is the percentage of functions which have been
           executed at least once. A function is considered to be executed if
           any of its instantiations are executed.'''),
    'region': (
        '''Region coverage is the percentage of code regions which have been
           executed at least once. A code region may span multiple lines (e.g in
           a large function body with no control flow). However, it's also
           possible for a single line to contain multiple code regions (e.g in
           'return x || y &amp;&amp; z').'''),
    'branch': (
        '''Branch coverage is the percentage of branches from each decision
           point is executed at least once.'''),
    'instruction': (
        '''Java instruction coverage is the percentage of the Java byte code
           instructions which have been executed at least once.'''),
}


def GetMetricsBasedOnCoverageTool(coverage_tool):
  """Gets a list of metrics for the given coverage tool.

  Args:
    coverage_tool(str): Name of the coverage tool, such as clang and jacoco.

  Returns:
    A list of dict of following format:
    {'name': clang, 'detail': blala}, where the name is the name of the metric
    and detail is an explanation of what the metric stands for.
  """
  assert coverage_tool in ('clang', 'jacoco'), (
      'Unrecognized coverage tool: %s' % coverage_tool)

  metrics = []
  if coverage_tool == 'clang':
    metrics = ['line', 'function', 'region']
  else:
    metrics = ['line', 'branch', 'instruction']

  return [{
      'name': m,
      'detail': _METRIC_NAME_DETAIL_MAPPING.get(m, '')
  } for m in metrics]
