# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from analysis.analysis_testcase import AnalysisTestCase
from analysis.chromecrash_parser import ChromeCrashParser
from analysis.chrome_crash_data import ChromeCrashData
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

  @mock.patch('analysis.chromecrash_parser.ChromeCrashParser.Parse')
  @mock.patch('libs.deps.chrome_dependency_fetcher.'
              'ChromeDependencyFetcher.GetDependency')
  def testParseStacktraceFailed(self, mock_get_dependency,
                                mock_chromecrash_parser):
    """Tests that ``stacktrace`` is None when failed to pars stacktrace."""
    mock_get_dependency.return_value = {}
    mock_chromecrash_parser.return_value = None
    crash_data = ChromeCrashData(
        self.GetDummyChromeCrashData(),
        ChromeDependencyFetcher(self.GetMockRepoFactory()))
    self.assertIsNone(crash_data.stacktrace)

  @mock.patch('libs.deps.chrome_dependency_fetcher.'
              'ChromeDependencyFetcher.GetDependency')
  def testParseStacktraceSucceeded(self, mock_get_dependency):
    """Tests parsing ``stacktrace``."""
    mock_get_dependency.return_value = {}
    crash_data = ChromeCrashData(
        self.GetDummyChromeCrashData(),
        ChromeDependencyFetcher(self.GetMockRepoFactory()))
    stack = CallStack(0)
    stacktrace = Stacktrace([stack], stack)
    with mock.patch(
        'analysis.chromecrash_parser.ChromeCrashParser.Parse') as mock_parse:
      mock_parse.return_value = stacktrace
      self._VerifyTwoStacktracesEqual(crash_data.stacktrace, stacktrace)

  def testParseStacktraceReturnsCache(self):
    """Tests that ``stacktrace`` returns cached ``_stacktrace`` value."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    stack = CallStack(1)
    stacktrace = Stacktrace([stack], stack)
    crash_data._stacktrace = stacktrace
    self._VerifyTwoStacktracesEqual(crash_data.stacktrace, stacktrace)

  def testDetectRegressionRangeFailed(self):
    """Tests that ``regression_range`` is None when detection failed."""
    crash_data = ChromeCrashData(
        self.GetDummyChromeCrashData(),
        ChromeDependencyFetcher(self.GetMockRepoFactory()))

    with mock.patch('analysis.detect_regression_range.DetectRegressionRange',
                    lambda *_: None):
      self.assertIsNone(crash_data.regression_range)

  def testDetectRegressionRangeSucceeded(self):
    """Tests detecting ``regression_range``."""
    crash_data = ChromeCrashData(
        self.GetDummyChromeCrashData(),
        ChromeDependencyFetcher(self.GetMockRepoFactory()))

    regression_range = ('1', '3')
    with mock.patch('analysis.detect_regression_range.DetectRegressionRange',
                    lambda *_: regression_range):
      self.assertEqual(crash_data.regression_range, regression_range)

  def testDetectRegressionRangeReturnsCache(self):
    """Tests that ``regression_range`` returns cached ``_regression_range``."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    regression_range = ('1', '5')
    crash_data._regression_range = regression_range
    self.assertEqual(crash_data.regression_range, regression_range)

  def testCrashedVersionDepsReturnsCache(self):
    """Tests that ``_CrashedVersionDeps`` returns cached value."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    crashed_version_deps = {'src/': Dependency('src/', 'https://repo', 'rev')}
    crash_data._crashed_version_deps = crashed_version_deps
    self.assertEqual(crash_data._CrashedVersionDeps(), crashed_version_deps)

  def testDependencies(self):
    """Tests that ``dependencies`` returns filtered ``_CrashedVersionDeps``."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    chromium_dep = Dependency('src/', 'https://repo', 'rev1')
    crash_data._crashed_version_deps = {
        chromium_dep.path: chromium_dep,
        'src/dummy': Dependency('src/dummy', 'https://r', 'rev2')}
    stack = CallStack(0, frame_list=[
        StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [5])])
    stacktrace = Stacktrace([stack], stack)
    crash_data._stacktrace = stacktrace
    self.assertEqual(crash_data.dependencies,
                     {chromium_dep.path: chromium_dep})

  def testReturnEmptyDependenciesIfEmptyStacktrace(self):
    """Tests that ``dependencies`` returns {} when stacktrace is None."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    self.assertEqual(crash_data.dependencies, {})

  def testDependenciesReturnsCache(self):
    """Tests that ``dependencies`` returns cached ``_dependencies`` value."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    crashed_version_deps = {'src/': Dependency('src/', 'https://repo', 'rev')}
    crash_data._dependencies = crashed_version_deps
    self.assertEqual(crash_data.dependencies, crashed_version_deps)

  def testDependencyRollsReturnsCache(self):
    """Tests that ``dependency_rolls`` returns cached ``_dependency_rolls``."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    dep_roll = {'src/': DependencyRoll('src/', 'https://repo', 'rev0', 'rev3')}
    crash_data._dependency_rolls = dep_roll
    self.assertEqual(crash_data.dependency_rolls, dep_roll)

  def testDependencyRollsWhenRegressionRangeIsEmpty(self):
    """Tests that ``regression_rolls`` is {} when regression_range is empty."""
    crash_data = ChromeCrashData(self.GetDummyChromeCrashData(), None)
    crash_data._regression_range = None
    self.assertEqual(crash_data.dependency_rolls, {})

  def testDependencyRoll(self):
    """Tests parsing ``regression_rolls`` from regression_range."""
    dep_roll = DependencyRoll('src/', 'https://repo', 'rev1', 'rev6')
    regression_rolls = {
        dep_roll.path: dep_roll,
        'src/dummy': DependencyRoll('src/dummy', 'https://r', 'rev2', 'rev4'),
        'src/add': DependencyRoll('src/add', 'https://rr', None, 'rev5')
    }

    with mock.patch(
        'libs.deps.chrome_dependency_fetcher.ChromeDependencyFetcher'
        '.GetDependencyRollsDict') as mock_get_dependency_rolls:
      mock_get_dependency_rolls.return_value = regression_rolls

      crash_data = ChromeCrashData(
          self.GetDummyChromeCrashData(),
          ChromeDependencyFetcher(self.GetMockRepoFactory()))

      crash_data._regression_range = ('rev1', 'rev6')
      chromium_dep = Dependency('src/', 'https://repo', 'rev1')
      crash_data._crashed_version_deps = {
          chromium_dep.path: chromium_dep,
          'src/dummy': Dependency('src/dummy', 'https://r', 'rev2')}
      stack = CallStack(0, frame_list=[
          StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [5])])
      stacktrace = Stacktrace([stack], stack)
      crash_data._stacktrace = stacktrace

      self.assertEqual(crash_data.dependency_rolls, {dep_roll.path: dep_roll})
