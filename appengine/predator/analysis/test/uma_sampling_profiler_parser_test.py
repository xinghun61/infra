# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from analysis.analysis_testcase import AnalysisTestCase
from analysis.stacktrace import CalleeLine
from analysis.stacktrace import ProfilerStackFrame
from analysis.type_enums import CallStackFormatType
from analysis.type_enums import LanguageType
from analysis.uma_sampling_profiler_parser import UMASamplingProfilerParser
from libs.deps.dependency import Dependency


class UMASamplingProfilerParserTest(AnalysisTestCase):

  def testReturnNoneForEmptyStacktrace(self):
    parser = UMASamplingProfilerParser()
    stacks = [{"frames": []}]
    deps = {'chrome/': Dependency('chrome/', 'https://repo', '1')}
    self.assertIsNone(parser.Parse(stacks, deps))

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
    deps = {'chrome/': Dependency('chrome/', 'https://repo', '1')}
    stacktrace = parser.Parse(stacks, deps)

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
    deps = {'chrome/': Dependency('chrome/', 'https://repo', '1')}
    stacktrace = parser.Parse(stacks, deps)
    self.assertEqual(stacktrace.stacks[0].language_type, LanguageType.JAVA)

