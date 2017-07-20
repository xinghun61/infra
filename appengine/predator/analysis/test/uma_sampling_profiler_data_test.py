# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock

from analysis import stacktrace
from analysis.analysis_testcase import AnalysisTestCase
from analysis.uma_sampling_profiler_data import UMASamplingProfilerData
from libs.deps.chrome_dependency_fetcher import ChromeDependencyFetcher
from libs.deps.dependency import Dependency
from libs.deps.dependency import DependencyRoll

TEST_DATA = {
  'thread_type': 'UI_THREAD',
  'collection_trigger': 'PROCESS_STARTUP',
  'process_type': 'BROWSER_PROCESS',
  'startup_phase': 'MAIN_LOOP_START',
  'platform': 'win',
  'subtree_stacks': [
    {
      'frames': [
        {
          'responsible': False,
          'filename': 'chrome/app/chrome_exe_main_win.cc',
          'difference': 0.1,
          'log_change_factor': float('inf'),
          'function_name': 'wWinMain',
          'function_start_line': 484,
          'lines': [
              [
                  {'line': 490, 'sample_fraction': 0.7},
                  {'line': 511, 'sample_fraction': 0.3},
              ],
              [
                  {'line': 490, 'sample_fraction': 0.9},
                  {'line': 511, 'sample_fraction': 0.1},
              ],
          ]
        },
        {
          'responsible': False,
          'filename': 'chrome/app/main_dll_loader_win.cc',
          'difference': 0.2,
          'log_change_factor': 6.1,
          'function_name': 'MainDllLoader::Launch(HINSTANCE__ *)',
          'function_start_line': 117,
        },
      ]
    },
    {
      'frames': [
        {
          'responsible': False,
          'filename': 'chrome/app/chrome_exe_main_win.cc',
          'difference': 0.3,
          'log_change_factor': float('inf'),
          'function_name': 'wWinMain',
          'function_start_line': 484,
        },
      ]
    }
  ],
  'subtree_id': 'AEF6F487C2EE7935',
  'subtree_root_depth': 0,
  'chrome_releases': [
    {
      'version': '54.0.2834.0',
      'channel': 'canary'
    },
    {
      'version': '54.0.2835.0',
      'channel': 'canary'
    }
  ]
}


class UMASamplingProfilerDataTest(AnalysisTestCase):

  def _GetDummyUMAData(self):
    return UMASamplingProfilerData(
        TEST_DATA, ChromeDependencyFetcher(self.GetMockRepoFactory()))

  def testTopLevelInfo(self):
    """Tests that the fields for top-level information are set correctly."""
    uma_data = self._GetDummyUMAData()
    self.assertEquals(uma_data.thread_type, 'UI_THREAD')
    self.assertEquals(uma_data.collection_trigger, 'PROCESS_STARTUP')
    self.assertEquals(uma_data.process_type, 'BROWSER_PROCESS')
    self.assertEquals(uma_data.startup_phase, 'MAIN_LOOP_START')
    self.assertEquals(uma_data.platform, 'win')
    self.assertEquals(uma_data.subtree_id, 'AEF6F487C2EE7935')
    self.assertEquals(uma_data.subtree_root_depth, 0)
    self.assertEquals(uma_data.chrome_releases,
                      [{'version': '54.0.2834.0', 'channel': 'canary'},
                       {'version': '54.0.2835.0', 'channel': 'canary'}])
    self.assertEquals(uma_data.crashed_version, '54.0.2835.0')
    self.assertEquals(uma_data.regression_range, ('54.0.2834.0', '54.0.2835.0'))
    self.assertEquals(uma_data.identifiers, {
        'platform': 'win',
        'process_type': 'BROWSER_PROCESS',
        'thread_type': 'UI_THREAD',
        'collection_trigger': 'PROCESS_STARTUP',
        'startup_phase': 'MAIN_LOOP_START',
        'chrome_releases': [{'version': '54.0.2834.0', 'channel': 'canary'},
                            {'version': '54.0.2835.0', 'channel': 'canary'}],
        'subtree_id': 'AEF6F487C2EE7935',
    })
    self.assertEquals(uma_data.signature, 'wWinMain')

  @mock.patch('libs.deps.chrome_dependency_fetcher.ChromeDependencyFetcher'
              '.GetDependency')
  def testStacktraceParsing(self, mock_get_dependency):
    """Test that ``stacktrace`` successfully parses a stacktrace."""
    mock_get_dependency.return_value = {
        'chrome/': Dependency('chrome/', 'https://repo', 'rev1')
    }

    uma_data = self._GetDummyUMAData()
    actual_stack_trace = uma_data.stacktrace

    stack_frame0 = stacktrace.ProfilerStackFrame(
        0, 0.1, float('inf'), False, 'chrome/', 'wWinMain',
        'app/chrome_exe_main_win.cc', 'chrome/app/chrome_exe_main_win.cc',
        'https://repo', 484,
        (stacktrace.FunctionLine(line=490, sample_fraction=0.7),
         stacktrace.FunctionLine(line=511, sample_fraction=0.3)),
        (stacktrace.FunctionLine(line=490, sample_fraction=0.9),
         stacktrace.FunctionLine(line=511, sample_fraction=0.1)))
    stack_frame1 = stacktrace.ProfilerStackFrame(
        1, 0.2, 6.1, False, 'chrome/', 'MainDllLoader::Launch(HINSTANCE__ *)',
        'app/main_dll_loader_win.cc', 'chrome/app/main_dll_loader_win.cc',
        'https://repo', 117, None)
    frames0 = (stack_frame0, stack_frame1)

    stack_frame2 = stacktrace.ProfilerStackFrame(
        0, 0.3, float('inf'), False, 'chrome/', 'wWinMain',
        'app/chrome_exe_main_win.cc', 'chrome/app/chrome_exe_main_win.cc',
        'https://repo', 484, None)
    frames1 = (stack_frame2,)

    call_stack0 = stacktrace.CallStack(0, frames0,
                                       stacktrace.CallStackFormatType.DEFAULT,
                                       stacktrace.LanguageType.CPP)
    call_stack1 = stacktrace.CallStack(0, frames1,
                                       stacktrace.CallStackFormatType.DEFAULT,
                                       stacktrace.LanguageType.CPP)
    stacks = (call_stack0, call_stack1)
    expected_stacktrace = stacktrace.Stacktrace(stacks, call_stack0)

    self._VerifyTwoStackFramesEqual(actual_stack_trace.stacks[0].frames[0],
                                    stack_frame0)
    self._VerifyTwoStacktracesEqual(actual_stack_trace, expected_stacktrace)

  @mock.patch('analysis.uma_sampling_profiler_parser.UMASamplingProfilerParser'
              '.Parse')
  @mock.patch('libs.deps.chrome_dependency_fetcher.'
              'ChromeDependencyFetcher.GetDependency')
  def testParseStacktraceFailed(self, mock_get_dependency,
                                mock_parse_stacktrace):
    """Tests that ``stacktrace`` is None when failed to parse stacktrace."""
    mock_get_dependency.return_value = {}
    mock_parse_stacktrace.return_value = None
    uma_data = self._GetDummyUMAData()
    self.assertIsNone(uma_data.stacktrace)

  @mock.patch('analysis.uma_sampling_profiler_data.UMASamplingProfilerData'
              '.stacktrace', new_callable=mock.PropertyMock)
  @mock.patch('analysis.dependency_analyzer.DependencyAnalyzer.GetDependencies')
  def testDependencies(self, mock_get_dependencies, mock_stacktrace):
    """Tests that ``dependencies``` calls GetDependencies."""
    uma_data = self._GetDummyUMAData()
    dependencies = {'src/': Dependency('src/', 'https://repo', 'rev')}
    mock_get_dependencies.return_value = dependencies
    stack = stacktrace.CallStack(0, frame_list=[
        stacktrace.StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [5])])
    stacktrace_field = stacktrace.Stacktrace([stack], stack)
    mock_stacktrace.return_value = stacktrace_field

    self.assertEqual(uma_data.dependencies, dependencies)
    mock_get_dependencies.assert_called_with(uma_data.stacktrace.stacks)

  @mock.patch('analysis.uma_sampling_profiler_data.UMASamplingProfilerData'
              '.stacktrace', new_callable=mock.PropertyMock)
  @mock.patch(
      'analysis.dependency_analyzer.DependencyAnalyzer.GetDependencyRolls')
  def testDependencyRolls(self, mock_get_dependency_rolls, mock_stacktrace):
    """Tests that ``dependency_rolls``` calls GetDependencyRolls."""
    uma_data = self._GetDummyUMAData()
    dep_roll = {'src/': DependencyRoll('src/', 'https://repo', 'rev0', 'rev3')}
    mock_get_dependency_rolls.return_value = dep_roll
    stack = stacktrace.CallStack(0, frame_list=[
        stacktrace.StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [5])])
    stacktrace_field = stacktrace.Stacktrace([stack], stack)
    mock_stacktrace.return_value = stacktrace_field

    self.assertEqual(uma_data.dependency_rolls, dep_roll)
    mock_get_dependency_rolls.assert_called_with(uma_data.stacktrace.stacks)
