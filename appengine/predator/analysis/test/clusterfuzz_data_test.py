# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from analysis.analysis_testcase import AnalysisTestCase
from analysis.clusterfuzz_data import ClusterfuzzData
from analysis.clusterfuzz_data import GetCommitCountInRegressionRange
from analysis.clusterfuzz_parser import ClusterfuzzParser
from analysis.stacktrace import CallStack
from analysis.stacktrace import StackFrame
from analysis.stacktrace import Stacktrace
from analysis.type_enums import CrashClient
from analysis.type_enums import SanitizerType
from libs.deps.chrome_dependency_fetcher import ChromeDependencyFetcher
from libs.deps.dependency import Dependency
from libs.deps.dependency import DependencyRoll


class CusterfuzzDataTest(AnalysisTestCase):
  """Tests ``ClusterfuzzData`` class."""

  def testProperties(self):
    """Tests ``ClusterfuzzData`` specific properties."""
    raw_crash_data = self.GetDummyClusterfuzzData(sanitizer='ASAN')
    crash_data = ClusterfuzzData(raw_crash_data, self.GetMockRepoFactory())
    self.assertEqual(crash_data.crash_address,
                     raw_crash_data['customized_data']['crash_address'])
    self.assertEqual(crash_data.crash_type,
                     raw_crash_data['customized_data']['crash_type'])
    self.assertEqual(crash_data.sanitizer,
                     SanitizerType.ADDRESS_SANITIZER)
    self.assertEqual(crash_data.job_type,
                     raw_crash_data['customized_data']['job_type'])
    self.assertEqual(crash_data.regression_range,
                     raw_crash_data['customized_data']['regression_range'])
    self.assertEqual(crash_data.testcase_id,
                     raw_crash_data['customized_data']['testcase_id'])
    self.assertEqual(crash_data.security_flag,
                     raw_crash_data['customized_data']['security_flag'])

  @mock.patch('analysis.clusterfuzz_parser.ClusterfuzzParser.Parse')
  def testParseStacktraceFailed(self, mock_parse):
    """Tests that ``stacktrace`` is None when failed to pars stacktrace."""
    mock_parse.return_value = None
    crash_data = ClusterfuzzData(self.GetDummyClusterfuzzData(),
                                 self.GetMockRepoFactory())
    self.assertIsNone(crash_data.stacktrace)

  def testParseStacktraceSucceeded(self):
    """Tests parsing ``stacktrace``."""
    crash_data = ClusterfuzzData(self.GetDummyClusterfuzzData(),
                                 self.GetMockRepoFactory())
    stack = CallStack(0)
    stacktrace = Stacktrace([stack], stack)
    with mock.patch(
        'analysis.clusterfuzz_parser.ClusterfuzzParser.Parse') as mock_parse:
      mock_parse.return_value = stacktrace
      self._VerifyTwoStacktracesEqual(crash_data.stacktrace, stacktrace)

  def testDependencies(self):
    """Tests ``dependencies`` property."""
    dep = Dependency('src/', 'https://repo', 'rev1')
    crash_data = ClusterfuzzData(self.GetDummyClusterfuzzData(
        dependencies=[{'dep_path': dep.path,
                       'repo_url': dep.repo_url,
                       'revision': dep.revision}]),
                                 self.GetMockRepoFactory())

    self.assertEqual(len(crash_data.dependencies), 1)
    self.assertTrue(dep.path in crash_data.dependencies)
    self.assertEqual(crash_data.dependencies[dep.path].path, dep.path)
    self.assertEqual(crash_data.dependencies[dep.path].repo_url, dep.repo_url)
    self.assertEqual(crash_data.dependencies[dep.path].revision, dep.revision)

  def testDependencyRolls(self):
    """Tests ``regression_rolls`` property."""
    dep_roll = DependencyRoll('src/', 'https://repo', 'rev1', 'rev6')
    crash_data = ClusterfuzzData(self.GetDummyClusterfuzzData(
        dependency_rolls=[{'dep_path': dep_roll.path,
                           'repo_url': dep_roll.repo_url,
                           'old_revision': dep_roll.old_revision,
                           'new_revision': dep_roll.new_revision}]),
                                 self.GetMockRepoFactory())

    self.assertEqual(len(crash_data.dependency_rolls), 1)
    self.assertTrue(dep_roll.path in crash_data.dependency_rolls)
    self.assertEqual(crash_data.dependency_rolls[dep_roll.path].path,
                     dep_roll.path)
    self.assertEqual(crash_data.dependency_rolls[dep_roll.path].repo_url,
                     dep_roll.repo_url)
    self.assertEqual(crash_data.dependency_rolls[dep_roll.path].old_revision,
                     dep_roll.old_revision)
    self.assertEqual(crash_data.dependency_rolls[dep_roll.path].new_revision,
                     dep_roll.new_revision)

  def testIdentifiers(self):
    crash_data = ClusterfuzzData(
        self.GetDummyClusterfuzzData(), self.GetMockRepoFactory())

    self.assertEqual(crash_data.identifiers, crash_data.testcase_id)

  def testRegressionRangeProperty(self):
    regression_range = {'dep_path': 'src', 'repo_url': 'https://repo',
                        'old_revision': 'rev0', 'new_revision': 'rev3'}
    crash_data = ClusterfuzzData(
        self.GetDummyClusterfuzzData(regression_range=regression_range),
        self.GetMockRepoFactory())

    self.assertEqual(crash_data.regression_range,
                     (regression_range['old_revision'],
                      regression_range['new_revision']))

    self.assertEqual(crash_data.regression_repository, regression_range)

  def testGetCommitCountInRegressionRange(self):
    """Tests ``GetCommitCountInRegressionRange`` function."""
    regression_range = {'repo_url': 'http://repo',
                        'repo_path': 'src',
                        'old_revision': 'rev2',
                        'new_revision': 'rev7'}

    def GetRepository(_):

      class MockRepository(object):
        def GetCommitsBetweenRevisions(self, *_):
          return ['rev1', 'rev2', 'rev3']

      return MockRepository()

    self.assertEqual(
        GetCommitCountInRegressionRange(
            GetRepository,
            regression_range['repo_url'], regression_range['old_revision'],
            regression_range['new_revision']), 3)

  @mock.patch('analysis.clusterfuzz_data.GetCommitCountInRegressionRange')
  def testCommitCountInRegressionRangeProperty(self, mock_get_commits):
    """Tests ``commit_count_in_regression_range`` property."""
    mock_get_commits.return_value = 6
    regression_range = {'dep_path': 'src', 'repo_url': 'https://repo',
                        'old_revision': 'rev0', 'new_revision': 'rev3'}
    crash_data = ClusterfuzzData(
        self.GetDummyClusterfuzzData(regression_range=regression_range),
        self.GetMockRepoFactory())

    self.assertEqual(crash_data.commit_count_in_regression_range, 6)
