# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.analysis_testcase import AnalysisTestCase
from analysis.stacktrace import CallStack
from analysis.stacktrace import ProfilerStackFrame
from analysis.type_enums import CallStackFormatType
from analysis.type_enums import LanguageType
from analysis.uma_sampling_profiler_parser import UMASamplingProfilerParser
from libs.deps.dependency import Dependency


class UMASamplingProfilerParserTest(AnalysisTestCase):

  def testReturnNoneForEmptyStacktrace(self):
    parser = UMASamplingProfilerParser()
    stacks = [{"frames": []}]
    deps = {'chrome': Dependency('chrome', 'https://repo', '1')}
    self.assertIsNone(parser.Parse(stacks, 0, deps))

  def testParseStacktrace(self):
    """Tests successfully parsing a stacktrace with two stacks."""
    parser = UMASamplingProfilerParser()
    stacks = [
        { # first stack
            "frames": [
                { # first frame
                    "difference": 0.01,
                    "log_change_factor": -8.1,
                    "responsible": False,
                },
                { # second frame
                    "difference": 0.02,
                    "log_change_factor": 5.3,
                    "responsible": True,
                },
            ]
        },
        { # second stack
            "frames": [
                {
                    "difference": 0.01,
                    "log_change_factor": -8.1,
                    "responsible": False,
                },
            ]
        },
    ]
    deps = {'chrome': Dependency('chrome', 'https://repo', '1')}
    stacktrace = parser.Parse(stacks, 0, deps)

    self.assertEqual(len(stacktrace), 2)
    self.assertEqual(len(stacktrace.stacks[0]), 2)
    self.assertEqual(len(stacktrace.stacks[1]), 1)

    expected_crash_stack = stacktrace.stacks[0].frames[0]
    self.assertEqual(stacktrace.crash_stack.frames[0], expected_crash_stack)
    self.assertEqual(stacktrace.stacks[0].priority, 0)
    self.assertEqual(stacktrace.stacks[0].language_type, LanguageType.CPP)
    self.assertEqual(stacktrace.stacks[0].format_type,
                     CallStackFormatType.DEFAULT)

  def testParseJavaFrame(self):
    """Tests that the language_type is set properly when given a Java frame."""
    parser = UMASamplingProfilerParser()
    stacks = [{"frames": [{
        "difference": 0.01,
        "log_change_factor": -8.1,
        "responsible": False,
        "filename": "chrome/app/chrome_exe_main_win.java",
    }]}]
    deps = {'chrome': Dependency('chrome', 'https://repo', '1')}
    stacktrace = parser.Parse(stacks, 0, deps)
    self.assertEqual(stacktrace.stacks[0].language_type, LanguageType.JAVA)

  def testFilterFramesBeforeSubtree(self):
    """Tests that the frames before the subtree root are filtered out."""
    parser = UMASamplingProfilerParser()
    frame1 = {
        'difference': 0, 'log_change_factor': 0, 'responsible': False
    }
    frame2 = {
        'difference': 0.1, 'log_change_factor': 0.1, 'responsible': True
    }
    subtree_root_depth = 2
    subtree_stacks = [
        # In this case the root is the first ``frame2`` instance.
        {'frames': [frame1, frame1, frame2, frame2]},
        {'frames': [frame1, frame1, frame2, frame2, frame2]},
    ]
    deps = {'chrome': Dependency('chrome', 'https://repo', '1')}

    stacktrace = parser.Parse(subtree_stacks, subtree_root_depth, deps)

    filtered_stacks = (
        CallStack(0, [
            ProfilerStackFrame(2, 0.1, 0.1, True),
            ProfilerStackFrame(3, 0.1, 0.1, True),
        ]),
        CallStack(0, [
            ProfilerStackFrame(2, 0.1, 0.1, True),
            ProfilerStackFrame(3, 0.1, 0.1, True),
            ProfilerStackFrame(4, 0.1, 0.1, True),
        ]),
    )
    self.assertEqual(stacktrace.stacks, filtered_stacks)

  def testFilteringIncludesExtraFrameInShiftCase(self):
    """Tests that one extra frame is included in a 'shift' case.

    In a 'shift' case (i.e. where execution time at the root has shifted
    entirely from one function to another), the subtree and one extra frame
    above it should be included.
    """
    parser = UMASamplingProfilerParser()
    frame1 = {
      'difference': 0, 'log_change_factor': 0, 'responsible': False
    }
    frame2 = {
      'difference': 0.1, 'log_change_factor': float('inf'), 'responsible': True
    }
    frame3 = {
      'difference': 0.1, 'log_change_factor': float('-inf'), 'responsible': True
    }
    subtree_root_depth = 2
    subtree_stacks = [
      # In this case the root is the first ``frame2`` or ``frame3`` instance.
      {'frames': [frame1, frame1, frame2, frame2]},
      {'frames': [frame1, frame1, frame3, frame3, frame3]},
    ]
    deps = {'chrome/': Dependency('chrome/', 'https://repo', '1')}

    stacktrace = parser.Parse(subtree_stacks, subtree_root_depth, deps)

    filtered_stacks = (
      CallStack(0, [
        ProfilerStackFrame(1, 0.0, 0.0, False), # extra node
        ProfilerStackFrame(2, 0.1, float('inf'), True),
        ProfilerStackFrame(3, 0.1, float('inf'), True),
      ]),
      CallStack(0, [
        ProfilerStackFrame(1, 0.0, 0.0, False), # extra node
        ProfilerStackFrame(2, 0.1, float('-inf'), True),
        ProfilerStackFrame(3, 0.1, float('-inf'), True),
        ProfilerStackFrame(4, 0.1, float('-inf'), True),
      ]),
    )
    self.assertEqual(stacktrace.stacks, filtered_stacks)
