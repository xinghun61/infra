# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy

from common.chrome_dependency_fetcher import ChromeDependencyFetcher
from common.dependency import Dependency
from common.dependency import DependencyRoll
from crash.crash_report import CrashReport
from crash.crash_report_with_dependencies import _FrozenDict
from crash.crash_report_with_dependencies import CrashReportWithDependencies
from crash.stacktrace import CallStack
from crash.stacktrace import StackFrame
from crash.stacktrace import Stacktrace
from crash.test.crash_test_suite import CrashTestSuite
from crash.type_enums import CallStackFormatType
from crash.type_enums import LanguageType
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.gitiles_repository import GitilesRepository

DUMMY_CHANGELOG1 = ChangeLog.FromDict({
    'author_name': 'r@chromium.org',
    'message': 'dummy',
    'committer_email': 'r@chromium.org',
    'commit_position': 175900,
    'author_email': 'r@chromium.org',
    'touched_files': [
        {
            'change_type': 'add',
            'new_path': 'a.cc',
            'old_path': None,
        },
    ],
    'author_time': 'Thu Mar 31 21:24:43 2016',
    'committer_time': 'Thu Mar 31 21:28:39 2016',
    'commit_url': 'https://repo.test/+/1',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'committer_name': 'example@chromium.org',
    'revision': '1',
    'reverted_revision': None
})

DUMMY_CHANGELOG2 = ChangeLog.FromDict({
    'author_name': 'example@chromium.org',
    'message': 'dummy',
    'committer_email': 'example@chromium.org',
    'commit_position': 175976,
    'author_email': 'example@chromium.org',
    'touched_files': [
        {
            'change_type': 'add',
            'new_path': 'f0.cc',
            'old_path': 'b/f0.cc'
        },
    ],
    'author_time': 'Thu Mar 31 21:24:43 2016',
    'committer_time': 'Thu Mar 31 21:28:39 2016',
    'commit_url': 'https://repo.test/+/2',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'committer_name': 'example@chromium.org',
    'revision': '2',
    'reverted_revision': '1'
})

DUMMY_CHANGELOG3 = ChangeLog.FromDict({
    'author_name': 'e@chromium.org',
    'message': 'dummy',
    'committer_email': 'e@chromium.org',
    'commit_position': 176000,
    'author_email': 'e@chromium.org',
    'touched_files': [
        {
            'change_type': 'modify',
            'new_path': 'f.cc',
            'old_path': 'f.cc'
        },
        {
            'change_type': 'delete',
            'new_path': None,
            'old_path': 'f1.cc'
        },
    ],
    'author_time': 'Thu Apr 1 21:24:43 2016',
    'committer_time': 'Thu Apr 1 21:28:39 2016',
    'commit_url': 'https://repo.test/+/3',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'committer_name': 'example@chromium.org',
    'revision': '3',
    'reverted_revision': None
})

DUMMY_CALLSTACKS = [
    CallStack(0, [], CallStackFormatType.DEFAULT, LanguageType.CPP),
    CallStack(1, [], CallStackFormatType.DEFAULT, LanguageType.CPP)]
DUMMY_REPORT = CrashReport(
    None, None, None, Stacktrace(DUMMY_CALLSTACKS, DUMMY_CALLSTACKS[0]),
    (None, None))


class FrozenDictTest(CrashTestSuite):
  def testHash(self):
    """Test that ``_FrozenDict`` does not throw an exception in ``hash``."""
    try:
        _h = hash(_FrozenDict({'a': 1, 'b': 2, 'c': 3}))
    except TypeError as e: # pragma: no cover
      if 'unhashable type' in str(e):
        self.fail('_FrozenDict.__hash__ does not work')
      else:
        raise e


class CrashReportWithDependenciesTest(CrashTestSuite):

  def setUp(self):
    super(CrashReportWithDependenciesTest, self).setUp()
    self.get_repository = GitilesRepository.Factory(self.GetMockHttpClient())
    self.dep_fetcher = ChromeDependencyFetcher(self.get_repository)

    # These mocks are shared by many (but not all) tests.
    def empty_dict(*_): # pragma: no cover
      """Constant function that returns the empty dict for all inputs.

      We break this out rather than using a lambda just so that we can
      add the "no cover" pragma. We really don't care if some particular
      test doesn't call these mocks.
      """
      return {}
    self.mock(ChromeDependencyFetcher, 'GetDependencyRollsDict', empty_dict)
    self.mock(ChromeDependencyFetcher, 'GetDependency', empty_dict)

  def testMissingRegressionRange(self):
    """Test that ``__new__`` fails when the regression range is missing."""
    report = DUMMY_REPORT._replace(regression_range=None)
    self.assertIsNone(CrashReportWithDependencies(report, self.dep_fetcher))

  def testMissingLastGoodRevision(self):
    """Test that ``__new__`` ?? when the last-good revision is missing."""
    report = DUMMY_REPORT._replace(regression_range=(None, '5'))
    # TODO(wrengr): find something worthwhile to test here.
    self.assertIsNotNone(CrashReportWithDependencies(report, self.dep_fetcher))

  def testMissingFirstBadRevision(self):
    """Test that ``__new__`` ?? when the first-bad revision is missing."""
    report = DUMMY_REPORT._replace(regression_range=('4', None))
    # TODO(wrengr): find something worthwhile to test here.
    self.assertIsNotNone(CrashReportWithDependencies(report, self.dep_fetcher))

  def testRegressionRangeProperty(self):
    # Define some non-trivial crash report (i.e., not DUMMY_REPORT)
    callstack = CallStack(0)
    report = CrashReport(
        crashed_version = '5',
        signature = 'sig',
        platform = 'canary',
        stacktrace = Stacktrace([callstack], callstack),
        regression_range = ('4', '5'),
    )
    self.assertTupleEqual(
        report.regression_range,
        CrashReportWithDependencies(report, self.dep_fetcher).regression_range)

  def testSkipAddedAndDeletedRegressionRolls(self):
    # Zipping these up to reduce repetition and chance for typos.
    zipped_deps = [
        ('src/', 'https://chromium.googlesource.com/chromium/src.git',
            '4', '5', '6'),
        ('src/dep1', 'https://url_dep1', None, '9', '10'),
    ]

    deps = {
        dep_path: Dependency(dep_path, repo_url, current_revision)
        for dep_path, repo_url, _0, _1, current_revision
        in zipped_deps
    }
    self.mock(ChromeDependencyFetcher, 'GetDependency', lambda *_: deps)

    dep_rolls = {
        dep_path: DependencyRoll(dep_path, url, old_revision, new_revision)
        for dep_path, url, old_revision, new_revision, _ in zipped_deps
    }
    self.mock(ChromeDependencyFetcher, 'GetDependencyRollsDict',
              lambda *_: dep_rolls)

    # N.B., the crash_stack must be non-empty in order to get any deps/rolls.
    frames = [
        StackFrame(
            index, dep_path, 'func', 'a.cc', '%s/a.cc' % dep_path, [42], url)
        for index, (dep_path, url, _0, _1, _2) in enumerate(zipped_deps)
    ]
    callstack = CallStack(0, frames)
    report = CrashReportWithDependencies(
        CrashReport(
            crashed_version = '5',
            signature = 'sig',
            platform = 'canary',
            stacktrace = Stacktrace([callstack], callstack),
            regression_range = ('4', '5')),
        self.dep_fetcher)

    # Regression of a dep added/deleted (old_revision/new_revision is None) can
    # not be known for sure and this case rarely happens, so just filter them
    # out.
    expected_regression_deps_rolls = copy.deepcopy(dep_rolls)
    del expected_regression_deps_rolls['src/dep1']
    self.assertEqual(report.dependency_rolls, expected_regression_deps_rolls)
