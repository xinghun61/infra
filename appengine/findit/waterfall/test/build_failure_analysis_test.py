# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from testing_utils import testing

from common.blame import Blame
from common.blame import Region
from common.diff import ChangeType
from common.git_repository import GitRepository
from waterfall import build_failure_analysis
from waterfall.failure_signal import FailureSignal


class BuildFailureAnalysisTest(testing.AppengineTestCase):

  def testIsSameFile(self):
    self.assertTrue(build_failure_analysis._IsSameFile('a/b/x.cc', 'x.cc'))
    self.assertTrue(build_failure_analysis._IsSameFile('a/b/x.cc', 'b/x.cc'))
    self.assertTrue(build_failure_analysis._IsSameFile('a/b/x.cc', 'a/b/x.cc'))

    self.assertFalse(
        build_failure_analysis._IsSameFile('a/prefix_x.cc.', 'x.cc'))
    self.assertFalse(
        build_failure_analysis._IsSameFile('prefix_a/x.cc.', 'a/x.cc'))
    self.assertFalse(
        build_failure_analysis._IsSameFile('c/x.cc.', 'a/b/c/x.cc'))
    self.assertFalse(build_failure_analysis._IsSameFile('a/x.cc.', 'a/y.cc'))

  def testNormalizeObjectFile(self):
    cases = {
        'obj/a/T.x.o': 'a/x.o',
        'obj/a/T.x.y.o': 'a/x.y.o',
        'x.o': 'x.o',
        'obj/a/x.obj': 'a/x.obj',
        'a.cc.obj': 'a.cc.obj',
        'T.a.c.o': 'a.c.o',
        'T.a.o': 'a.o'
    }
    for obj_file, expected_file in cases.iteritems():
      self.assertEqual(
          expected_file,
          build_failure_analysis._NormalizeObjectFilePath(obj_file))

  def testStripCommonSuffix(self):
    cases = {
        'a_file':
            'a_file_%s.cc' % '_'.join(build_failure_analysis._COMMON_SUFFIXES),
        'src/b_file': 'src/b_file_impl_mac.h',
        'c_file': 'c_file_browsertest.cc',
        'xdtest': 'xdtest.cc',
    }
    for expected_file, file_path in cases.iteritems():
      self.assertEqual(
          expected_file,
          build_failure_analysis._StripExtensionAndCommonSuffix(file_path))

  def testIsRelated(self):
    self.assertTrue(build_failure_analysis._IsRelated('a.py', 'a_test.py'))
    self.assertTrue(
        build_failure_analysis._IsRelated('a.h', 'a_impl_test.o'))
    self.assertTrue(
        build_failure_analysis._IsRelated('a.h', 'target.a_impl_test.obj'))

    self.assertFalse(
        build_failure_analysis._IsRelated('a/x.cc', 'a/b/y.cc'))
    self.assertFalse(
        build_failure_analysis._IsRelated('a/x.cc', 'xdtest.cc'))
    self.assertFalse(
        build_failure_analysis._IsRelated('a_tests.cc', 'a_browsertests.cc'))
    self.assertFalse(
        build_failure_analysis._IsRelated('cc_unittests.isolate', 'a.cc.obj'))
    self.assertFalse(
        build_failure_analysis._IsRelated('a.h', 'a.pyc'))
    self.assertFalse(
        build_failure_analysis._IsRelated('a', 'b'))
    self.assertFalse(build_failure_analysis._IsRelated('a', 'a'))

  def testCheckFilesAgainstSuspectedCL(self):
    failure_signal_json = {
        'files': {
            'src/a/b/f1.cc': [],
            'd/e/a2_test.cc': [],
            'b/c/f2.cc': [10, 20],
            'd/e/f3.h': [],
            'x/y/f4.py': [],
            'f5_impl.cc': []
        }
    }
    change_log_json = {
        'revision': 'rev',
        'touched_files': [
            {
                'change_type': ChangeType.ADD,
                'old_path': '/dev/null',
                'new_path': 'a/b/f1.cc'
            },
            {
                'change_type': ChangeType.ADD,
                'old_path': '/dev/null',
                'new_path': 'd/e/a2.cc'
            },
            {
                'change_type': ChangeType.MODIFY,
                'old_path': 'a/b/c/f2.h',
                'new_path': 'a/b/c/f2.h'
            },
            {
                'change_type': ChangeType.MODIFY,
                'old_path': 'd/e/f3.h',
                'new_path': 'd/e/f3.h'
            },
            {
                'change_type': ChangeType.DELETE,
                'old_path': 'x/y/f4.py',
                'new_path': '/dev/null'
            },
            {
                'change_type': ChangeType.DELETE,
                'old_path': 'h/f5.h',
                'new_path': '/dev/null'
            },
            {
                'change_type': ChangeType.RENAME,
                'old_path': 't/y/x.cc',
                'new_path': 's/z/x.cc'
            },
        ]
    }
    deps_info = {}

    justification = build_failure_analysis._CheckFiles(
        FailureSignal.FromDict(failure_signal_json),
        change_log_json, deps_info)
    self.assertIsNotNone(justification)
    # The score is 15 because:
    # +5 added a/b/f1.cc (same file src/a/b/f1.cc in failure_signal log)
    # +1 added d/e/a2.cc (related file a2_test.cc in failure_signal log)
    # +1 modified b/c/f2.h (related file a/b/c/f2.cc in failure_signal log)
    # +2 modified d/e/f3.h (same file d/e/f3.h in failure_signal log)
    # +5 deleted x/y/f4.py (same file x/y/f4.py in failure_signal log)
    # +1 deleted h/f5.h (related file f5_impl.cc in failure_signal log)
    # +0 renamed t/y/x.cc -> s/z/x.cc (no related file in failure_signal log)
    self.assertEqual(15, justification['score'])

  def testCheckFilesAgainstUnrelatedCL(self):
    failure_signal_json = {
        'files': {
            'src/a/b/f.cc': [],
        }
    }
    change_log_json = {
        'revision': 'rev',
        'touched_files': [
            {
                'change_type': ChangeType.ADD,
                'old_path': '/dev/null',
                'new_path': 'a/d/f1.cc'
            },
        ]
    }
    deps_info = {}

    justification = build_failure_analysis._CheckFiles(
        FailureSignal.FromDict(failure_signal_json),
        change_log_json, deps_info)
    self.assertIsNone(justification)

  def _MockGetBlame(self, path, revision):
    if revision == '10' or path == 'f_not_exist.cc':
      return None
    blame = Blame(revision, path)
    if revision <= '3':
      blame.AddRegion(Region(1, 10, '2',
                             u'test3@chromium.org', u'test3@chromium.org',
                             datetime(2015, 06, 02, 04, 35, 32)))
    else:
      blame.AddRegion(Region(1, 2, '7',
                             u'test3@chromium.org', u'test3@chromium.org',
                             datetime(2015, 06, 07, 04, 35, 32)))
      blame.AddRegion(Region(3, 3, '5',
                             u'test3@chromium.org', u'test3@chromium.org',
                             datetime(2015, 06, 05, 04, 35, 32)))
      blame.AddRegion(Region(7, 1, '8',
                             u'test2@chromium.org', u'test2@chromium.org',
                             datetime(2015, 06, 8, 04, 35, 32)))
      blame.AddRegion(Region(8, 1, '7',
                             u'test3@chromium.org', u'test3@chromium.org',
                             datetime(2015, 06, 07, 21, 35, 32)))
      blame.AddRegion(Region(9, 10, '12',
                             u'test3@chromium.org', u'test3@chromium.org',
                             datetime(2015, 06, 12, 04, 35, 32)))
    return blame

  def _MockGetChangeLog(self, revision):
    class MockChangeLog(object):

      def __init__(self, date):
        self.author_time = datetime.strptime(
            'Jun %s 04:35:32 2015' % date, '%b %d %H:%M:%S %Y')

    return MockChangeLog(revision)

  def _testCheckFileInDependencyRoll(
      self, file_path_in_log, rolls, expected_score, line_numbers,
      expected_hints=None):
    self.mock(GitRepository, 'GetChangeLog', self._MockGetChangeLog)
    self.mock(GitRepository, 'GetBlame', self._MockGetBlame)
    justification = build_failure_analysis._Justification()
    build_failure_analysis._CheckFileInDependencyRolls(
        file_path_in_log, rolls, justification, line_numbers)
    self.assertEqual(expected_score, justification.score)
    if expected_hints:
      self.assertEqual(expected_hints, justification._hints)

  def testCheckFileInDependencyRollWhenUnrelatedDependencyIsRolled(self):
    file_path_in_log = 'third_party/dep/f.cc'
    rolls = [
        {  # An unrelated dependency was rolled to a new revision.
            'path': 'src/third_party/dep2/',
            'repo_url': 'https://url_dep2',
            'old_revision': '6',
            'new_revision': '8',
        },
    ]
    expected_score = 0

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        None)

  def testCheckFileInDependencyRollWhenRelatedDependencyIsRolled(self):
    file_path_in_log = 'third_party/dep/f.cc'
    rolls = [
        {  # Dependency was rolled to a new revision.
            'path': 'src/third_party/dep/',
            'repo_url': 'https://url_dep',
            'old_revision': '6',
            'new_revision': '8',
        },
    ]
    expected_score = 1
    expected_hints = {
        ('rolled dependency third_party/dep/ with changes in '
         'https://url_dep/+log/6..8?pretty=fuller (and f.cc was in log)'): 1
    }

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        None, expected_hints)

  def testCheckFileInDependencyRollWhenRelatedDependencyIsAdded(self):
    file_path_in_log = 'third_party/dep/f.cc'
    rolls = [
        {  # Dependency was newly-added.
            'path': 'src/third_party/dep/',
            'repo_url': 'https://url_dep',
            'old_revision': None,
            'new_revision': '9',
        },
    ]
    expected_score = 5

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        None)

  def testCheckFileInDependencyRollWhenRelatedDependencyIsDeleted(self):
    file_path_in_log = 'third_party/dep/f.cc'
    rolls = [
        {  # Dependency was deleted.
            'path': 'src/third_party/dep/',
            'repo_url': 'https://url_dep',
            'old_revision': '7',
            'new_revision': None,
        },
    ]
    expected_score = 5

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        None)

  def testCheckFileInDependencyRollWhenFileIsAddedWithinTheRoll(self):
    rolls = [
        {  # One region in blame.
            'path': 'src/third_party/dep/',
            'repo_url': 'https://url_dep',
            'old_revision': '1',
            'new_revision': '2',
        }
    ]
    file_path_in_log = 'third_party/dep/f.cc'
    expected_score = 5
    expected_hints = {
        ('rolled dependency third_party/dep/ with changes in '
         'https://url_dep/+log/1..2?pretty=fuller '
         '(and f.cc(new file) was in log)'): 5
    }

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        None, expected_hints)

  def testCheckFileInDependencyRollWhenFileIsAddedAndChangedWithinTheRoll(self):
    file_path_in_log = 'third_party/dep/f.cc'
    rolls = [
        {  # Multiple regions in blame, but they are all after old revision.
            'path': 'src/third_party/dep/',
            'repo_url': 'https://url_dep',
            'old_revision': '4',
            'new_revision': '9',
        },
    ]
    expected_score = 5

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        None)

  def testCheckFileInDependencyRollWhenFileIsNotAddedWithinTheRoll(self):
    rolls = [{
        'path': 'src/third_party/dep/',
        'repo_url': 'https://url_dep',
        'old_revision': '2',
        'new_revision': '3',
    }]
    file_path_in_log = 'third_party/dep/f.cc'
    expected_score = 0

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        None)

  def testCheckFileInDependencyRollWhenLinesAreChangedWithinTheRoll(self):
    rolls = [{
        'path': 'src/third_party/dep/',
        'repo_url': 'https://url_dep',
        'old_revision': '6',
        'new_revision': '8',
    }]
    file_path_in_log = 'third_party/dep/f.cc'
    line_numbers = [2, 7, 8]
    expected_score = 4
    expected_hints = {
        ('rolled dependency third_party/dep/ with changes in '
         'https://url_dep/+log/6..8?pretty=fuller '
         '(and f.cc[2, 7, 8] was in log)'): 4
    }

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        line_numbers, expected_hints)

  def testCheckFileInDependencyRollWhenFileIsNotChanged(self):
    rolls = [{
        'path': 'src/third_party/dep/',
        'repo_url': 'https://url_dep',
        'old_revision': '8',
        'new_revision': '9',
    }]
    file_path_in_log = 'third_party/dep/f.cc'
    line_numbers = [2, 7, 8]
    expected_score = 0

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        line_numbers)

  def testCheckFileInDependencyRollRolledDowngrade(self):
    rolls = [{
        'path': 'src/third_party/dep/',
        'repo_url': 'https://url_dep',
        'old_revision': '8',
        'new_revision': '6',
    }]
    file_path_in_log = 'third_party/dep/f.cc'
    line_numbers = [2, 7, 8]
    expected_score = 0

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        line_numbers)

  def testCheckFileInDependencyRollFileNotExist(self):
    rolls = [{
        'path': 'src/third_party/dep/',
        'repo_url': 'https://url_dep',
        'old_revision': '6',
        'new_revision': '8',
    }]
    file_path_in_log = 'third_party/dep/f_not_exist.cc'
    line_numbers = [2, 7, 8]
    expected_score = 0

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        line_numbers)

  def testCheckFileInDependencyRollOnV8(self):
    rolls = [{
        'path': 'src/v8/',
        'repo_url': 'https://chromium.googlesource.com/v8/v8.git',
        'old_revision': '6',
        'new_revision': '8',
    }]
    file_path_in_log = 'v8/f.cc'
    line_numbers = [2, 7, 8]
    expected_score = 0

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        line_numbers)

  def testCheckFilesAgainstDEPSRoll(self):
    failure_signal_json = {
        'files': {
            'src/third_party/dep1/f.cc': [123],
        }
    }
    change_log_json = {
        'revision': 'rev',
        'touched_files': [
            {
                'change_type': ChangeType.MODIFY,
                'old_path': 'DEPS',
                'new_path': 'DEPS'
            },
        ]
    }
    deps_info = {
        'deps_rolls': {
            'rev': [
                {
                    'path': 'src/third_party/dep1/',
                    'repo_url': 'https://url_dep1',
                    'old_revision': '7',
                    'new_revision': '9',
                },
            ]
        }
    }
    self.mock(GitRepository, 'GetChangeLog', self._MockGetChangeLog)
    self.mock(GitRepository, 'GetBlame', self._MockGetBlame)
    justification = build_failure_analysis._CheckFiles(
        FailureSignal.FromDict(failure_signal_json),
        change_log_json, deps_info)
    self.assertIsNotNone(justification)
    # The score is 1 because:
    # +1 rolled third_party/dep1/ and src/third_party/dep1/f.cc was in log.
    self.assertEqual(1, justification['score'])

  def testAnalyzeSuccessfulBuild(self):
    failure_info = {
        'failed': False,
    }
    result = build_failure_analysis.AnalyzeBuildFailure(
        failure_info, change_logs=None, deps_info=None, failure_signals=None)
    self.assertEqual(0, len(result['failures']))

  def testAnalyzeBuildWithoutValidChromiumRevision(self):
    failure_info = {
        'failed': True,
        'chromium_revision': None,
    }
    result = build_failure_analysis.AnalyzeBuildFailure(
        failure_info, change_logs=None, deps_info=None, failure_signals=None)
    self.assertEqual(0, len(result['failures']))

  def testAnalyzeBuildFailure(self):
    failure_info = {
        'failed': True,
        'chromium_revision': 'r99_2',
        'failed_steps': {
            'a': {
                'current_failure': 99,
                'first_failure': 98,
            },
            'b': {
                'current_failure': 99,
                'first_failure': 98,
                'last_pass': 96,
            },
        },
        'builds': {
            '99': {
                'blame_list': ['r99_1', 'r99_2'],
            },
            '98': {
                'blame_list': ['r98_1'],
            },
            '97': {
                'blame_list': ['r97_1'],
            },
            '96': {
                'blame_list': ['r96_1', 'r96_2'],
            },
        }
    }
    change_logs = {
        'r99_1': {
            'revision': 'r99_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_1.cc',
                    'new_path': 'a/b/f99_1.cc'
                },
            ],
        },
        'r99_2': {
            'revision': 'r99_2',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_2.cc',
                    'new_path': 'a/b/f99_2.cc'
                },
            ],
        },
        'r98_1': {
            'revision': 'r98_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'y/z/f98.cc',
                    'new_path': 'y/z/f98.cc'
                },
            ],
        },
        'r97_1': {
            'revision': 'r97_1',
            'touched_files': [
                {
                    'change_type': ChangeType.ADD,
                    'old_path': '/dev/null',
                    'new_path': 'x/y/f99_1.cc'
                },
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_1.cc',
                    'new_path': 'a/b/f99_1.cc'
                },
            ],
        },
        'r96_1': {
            'revision': 'r96_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f96_1.cc',
                    'new_path': 'a/b/f96_1.cc'
                },
            ],
        },
    }
    deps_info = {}
    failure_signals_json = {
        'a': {
            'files': {
                'src/a/b/f99_2.cc': [],
            },
        },
        'b': {
            'files': {
                'x/y/f99_1.cc': [],
            },
        },
    }
    expected_analysis_result = {
        'failures': [
            {
                'step_name': 'a',
                'first_failure': 98,
                'last_pass': None,
                'suspected_cls': [
                    {
                        'build_number': 99,
                        'repo_name': 'chromium',
                        'revision': 'r99_2',
                        'commit_position': None,
                        'url': None,
                        'score': 2,
                        'hints': {
                            'modified f99_2.cc (and it was in log)': 2,
                        },
                    }
                ],
            },
            {
                'step_name': 'b',
                'first_failure': 98,
                'last_pass': 96,
                'suspected_cls': [
                    {
                        'build_number': 97,
                        'repo_name': 'chromium',
                        'revision': 'r97_1',
                        'commit_position': None,
                        'url': None,
                        'score': 5,
                        'hints': {
                            'added x/y/f99_1.cc (and it was in log)': 5,
                        },
                    }
                ],
            }
        ]
    }

    analysis_result = build_failure_analysis.AnalyzeBuildFailure(
        failure_info, change_logs, deps_info, failure_signals_json)
    self.assertEqual(expected_analysis_result, analysis_result)

  def testGetGitBlame(self):
    repo_info = {
        'repo_url': 'https://chromium.googlesource.com/chromium/src.git',
        'revision': '8'
    }
    file_path = 'a/b/c.cc'
    self.mock(GitRepository, 'GetBlame', self._MockGetBlame)
    blame = build_failure_analysis._GetGitBlame(repo_info, file_path)
    self.assertIsNotNone(blame)

  def testGetGitBlameEmpty(self):
    repo_info = {}
    file_path = 'a/b/c.cc'
    self.mock(GitRepository, 'GetBlame', self._MockGetBlame)
    blame = build_failure_analysis._GetGitBlame(repo_info, file_path)
    self.assertIsNone(blame)

  def testGetChangedLinesTrue(self):
    repo_info = {
        'repo_url': 'https://chromium.googlesource.com/chromium/src.git',
        'revision': '8'
    }
    touched_file = {
        'change_type': ChangeType.MODIFY,
        'old_path': 'a/b/c.cc',
        'new_path': 'a/b/c.cc'
    }
    line_numbers = [2, 7, 8]
    commit_revision = '7'
    self.mock(GitRepository, 'GetBlame', self._MockGetBlame)
    changed_line_numbers = (
        build_failure_analysis._GetChangedLinesForChromiumRepo(
            repo_info, touched_file, line_numbers, commit_revision))

    self.assertEqual([2, 8], changed_line_numbers)

  def testGetChangedLinesDifferentRevision(self):
    repo_info = {
        'repo_url': 'https://chromium.googlesource.com/chromium/src.git',
        'revision': '9'
    }
    touched_file = {
        'change_type': ChangeType.MODIFY,
        'old_path': 'a/b/c.cc',
        'new_path': 'a/b/c.cc'
    }
    line_numbers = [2, 7, 8]
    commit_revision = '9'
    self.mock(GitRepository, 'GetBlame', self._MockGetBlame)
    changed_line_numbers = (
        build_failure_analysis._GetChangedLinesForChromiumRepo(
            repo_info, touched_file, line_numbers, commit_revision))

    self.assertEqual([], changed_line_numbers)

  def testGetChangedLinesDifferentLine(self):
    repo_info = {
        'repo_url': 'https://chromium.googlesource.com/chromium/src.git',
        'revision': '8'
    }
    touched_file = {
        'change_type': ChangeType.MODIFY,
        'old_path': 'a/b/c.cc',
        'new_path': 'a/b/c.cc'
    }
    line_numbers = [15]
    commit_revision = '7'
    self.mock(GitRepository, 'GetBlame', self._MockGetBlame)
    changed_line_numbers = (
        build_failure_analysis._GetChangedLinesForChromiumRepo(
            repo_info, touched_file, line_numbers, commit_revision))

    self.assertEqual([], changed_line_numbers)

  def testGetChangedLinesNoneBlame(self):
    repo_info = {
        'repo_url': 'https://chromium.googlesource.com/chromium/src.git',
        'revision': '10'
    }
    touched_file = {
        'change_type': ChangeType.MODIFY,
        'old_path': 'a/b/c.cc',
        'new_path': 'a/b/c.cc'
    }
    line_numbers = [2, 7, 8]
    commit_revision = '7'
    self.mock(GitRepository, 'GetBlame', self._MockGetBlame)
    changed_line_numbers = (
        build_failure_analysis._GetChangedLinesForChromiumRepo(
            repo_info, touched_file, line_numbers, commit_revision))

    self.assertEqual([], changed_line_numbers)

  def testCheckFileSameLineChanged(self):
    def MockGetChangedLines(*_):
      return [1, 3]
    self.mock(build_failure_analysis, '_GetChangedLinesForChromiumRepo',
              MockGetChangedLines)
    touched_file = {
        'change_type': ChangeType.MODIFY,
        'old_path': 'a/b/c.cc',
        'new_path': 'a/b/c.cc'
    }
    file_path_in_log = 'a/b/c.cc'
    justification = build_failure_analysis._Justification()
    file_name_occurrences = {'c.cc': 1}
    line_numbers = [1, 3]
    repo_info = {
        'repo_url': 'https://chromium.googlesource.com/chromium/src.git',
        'revision': 'dummy_abcd1234'
    }
    commit_revision = 'dummy_1'
    build_failure_analysis._CheckFile(
        touched_file, file_path_in_log, justification, file_name_occurrences,
        line_numbers, repo_info, commit_revision)

    expected_justification = {
        'score': 4,
        'hints': {
            'modified c.cc[1, 3] (and it was in log)': 4
        }
    }
    self.assertEqual(expected_justification, justification.ToDict())
