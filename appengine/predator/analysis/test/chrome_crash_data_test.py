# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from analysis.analysis_testcase import AnalysisTestCase
from analysis.chrome_crash_data import ChromeCrashData
from analysis.chrome_crash_data import CracasCrashData
from analysis.chrome_crash_data import FracasCrashData
from analysis.stacktrace import CallStack
from analysis.stacktrace import StackFrame
from analysis.stacktrace import Stacktrace
from libs.deps.chrome_dependency_fetcher import ChromeDependencyFetcher
from libs.deps.dependency import Dependency
from libs.deps.dependency import DependencyRoll


class ChromeCrashDataTest(AnalysisTestCase):
  """Tests ``ChromeCrashData`` class."""

  def testProperties(self):
    """Tests ``ChromeCrashData`` specific properties."""
    raw_crash_data = self.GetDummyChromeCrashData()
    crash_data = ChromeCrashData(raw_crash_data, None)
    self.assertEqual(crash_data.channel,
                     raw_crash_data['customized_data']['channel'])
    self.assertEqual(crash_data.historical_metadata,
                     raw_crash_data['customized_data']['historical_metadata'])

  def testDetectRegressionRangeFailed(self):
    """Tests that ``regression_range`` is None when detection failed."""
    with mock.patch('analysis.detect_regression_range.DetectRegressionRange',
                    lambda *_: None):
      crash_data = ChromeCrashData(
          self.GetDummyChromeCrashData(),
          ChromeDependencyFetcher(self.GetMockRepoFactory()))
      self.assertIsNone(crash_data.regression_range)

  def testDetectRegressionRangeSucceeded(self):
    """Tests detecting ``regression_range``."""
    regression_range = ('1', '3')
    with mock.patch('analysis.detect_regression_range.DetectRegressionRange',
                    lambda *_: regression_range):
      crash_data = ChromeCrashData(
          self.GetDummyChromeCrashData(),
          ChromeDependencyFetcher(self.GetMockRepoFactory()))
      self.assertEqual(crash_data.regression_range, regression_range)

  @mock.patch('analysis.chrome_crash_data.ChromeCrashData.stacktrace',
              new_callable=mock.PropertyMock)
  @mock.patch('analysis.dependency_analyzer.DependencyAnalyzer.GetDependencies')
  def testDependencies(self, mock_get_dependencies, mock_stacktrace):
    """Tests that ``dependencies`` calls GetDependencies."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    crashed_version_deps = {'src/': Dependency('src/', 'https://repo', 'rev')}
    mock_get_dependencies.return_value = crashed_version_deps
    stack = CallStack(0, frame_list=[
        StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [5])])
    stacktrace = Stacktrace([stack], stack)
    mock_stacktrace.return_value = stacktrace

    self.assertEqual(crash_data.dependencies, crashed_version_deps)
    mock_get_dependencies.assert_called_with(
        [crash_data.stacktrace.crash_stack])

  @mock.patch('analysis.chrome_crash_data.ChromeCrashData.stacktrace',
              new_callable=mock.PropertyMock)
  @mock.patch('analysis.dependency_analyzer.DependencyAnalyzer'
              '.GetDependencyRolls')
  def testDependencyRolls(self, mock_get_dependency_rolls, mock_stacktrace):
    """Tests that ``dependency_rolls`` calls GetDependencyRolls."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    dep_roll = {'src/': DependencyRoll('src/', 'https://repo', 'rev0', 'rev3')}
    mock_get_dependency_rolls.return_value = dep_roll
    stack = CallStack(0, frame_list=[
        StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [5])])
    stacktrace = Stacktrace([stack], stack)
    mock_stacktrace.return_value = stacktrace

    self.assertEqual(crash_data.dependency_rolls, dep_roll)
    mock_get_dependency_rolls.assert_called_with(
        [crash_data.stacktrace.crash_stack])

  def testIdentifiers(self):
    crash_data = ChromeCrashData(
        self.GetDummyChromeCrashData(),
        ChromeDependencyFetcher(self.GetMockRepoFactory()))

    self.assertDictEqual(
        crash_data.identifiers,
        {'signature': crash_data.signature,
         'platform': crash_data.platform,
         'channel': crash_data.channel,
         'regression_range': crash_data.regression_range})


class FracasCrashDataTest(AnalysisTestCase):
  """Tests ``FracasCrashData`` class."""

  @mock.patch('analysis.chromecrash_parser.FracasCrashParser.Parse')
  @mock.patch('libs.deps.chrome_dependency_fetcher.'
              'ChromeDependencyFetcher.GetDependency')
  def testParseStacktraceFailed(self, mock_get_dependency,
                                mock_chromecrash_parser):
    """Tests that ``stacktrace`` is None when failed to parse stacktrace."""
    mock_get_dependency.return_value = {}
    mock_chromecrash_parser.return_value = None
    crash_data = FracasCrashData(
        self.GetDummyChromeCrashData(),
        ChromeDependencyFetcher(self.GetMockRepoFactory()))
    self.assertIsNone(crash_data.stacktrace)

  @mock.patch('libs.deps.chrome_dependency_fetcher.'
              'ChromeDependencyFetcher.GetDependency')
  def testParseStacktraceSucceeded(self, mock_get_dependency):
    """Tests parsing ``stacktrace``."""
    mock_get_dependency.return_value = {}
    crash_data = FracasCrashData(
        self.GetDummyChromeCrashData(),
        ChromeDependencyFetcher(self.GetMockRepoFactory()))
    stack = CallStack(0)
    stacktrace = Stacktrace([stack], stack)
    with mock.patch(
        'analysis.chromecrash_parser.FracasCrashParser.Parse') as mock_parse:
      mock_parse.return_value = stacktrace
      self._VerifyTwoStacktracesEqual(crash_data.stacktrace, stacktrace)


class CracasCrashDataTest(AnalysisTestCase):
  """Tests ``CracasCrashData`` class."""

  @mock.patch('analysis.chromecrash_parser.CracasCrashParser.Parse')
  @mock.patch('libs.deps.chrome_dependency_fetcher.'
              'ChromeDependencyFetcher.GetDependency')
  def testParseStacktraceFailed(self, mock_get_dependency,
                                mock_chromecrash_parser):
    """Tests that ``stacktrace`` is None when failed to parse stacktrace."""
    mock_get_dependency.return_value = {}
    mock_chromecrash_parser.return_value = None
    crash_data = CracasCrashData(
        self.GetDummyChromeCrashData(),
        ChromeDependencyFetcher(self.GetMockRepoFactory()))
    self.assertIsNone(crash_data.stacktrace)

  @mock.patch('libs.deps.chrome_dependency_fetcher.'
              'ChromeDependencyFetcher.GetDependency')
  def testParseStacktraceSucceeded(self, mock_get_dependency):
    """Tests parsing ``stacktrace``."""
    mock_get_dependency.return_value = {}
    crash_data = CracasCrashData(
        self.GetDummyChromeCrashData(),
        ChromeDependencyFetcher(self.GetMockRepoFactory()))
    stack = CallStack(0)
    stacktrace = Stacktrace([stack], stack)
    with mock.patch(
        'analysis.chromecrash_parser.CracasCrashParser.Parse') as mock_parse:
      mock_parse.return_value = stacktrace
      self._VerifyTwoStacktracesEqual(crash_data.stacktrace, stacktrace)
