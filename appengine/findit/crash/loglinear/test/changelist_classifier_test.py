# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import math
import pprint

from common.dependency import DependencyRoll
from common import chrome_dependency_fetcher
from crash import changelist_classifier
from crash.crash_report import CrashReport
import crash.loglinear.changelist_classifier as loglinear_changelist_classifier
from crash.loglinear.feature import ChangedFile
from crash.loglinear.feature import FeatureValue
from crash.suspect import AnalysisInfo
from crash.suspect import Suspect
from crash.suspect import StackInfo
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
    'commit_url':
        'https://repo.test/+/1',
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
    'commit_url':
        'https://repo.test/+/2',
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
    'commit_url':
        'https://repo.test/+/3',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'committer_name': 'example@chromium.org',
    'revision': '3',
    'reverted_revision': None
})

DUMMY_CALLSTACKS = [CallStack(0, [],
                              CallStackFormatType.DEFAULT, LanguageType.CPP),
                    CallStack(1, [],
                              CallStackFormatType.DEFAULT, LanguageType.CPP)]
DUMMY_REPORT = CrashReport(None, None, None, Stacktrace(DUMMY_CALLSTACKS,
                                                        DUMMY_CALLSTACKS[0]),
                           (None, None))


class LogLinearChangelistClassifierTest(CrashTestSuite):

  def setUp(self):
    super(LogLinearChangelistClassifierTest, self).setUp()
    weights = {
        'MinDistance': 1.,
        'TopFrameIndex': 1.,
    }

    self.changelist_classifier = (
        loglinear_changelist_classifier.LogLinearChangelistClassifier(
          GitilesRepository(self.GetMockHttpClient()), weights))

  def testAggregateChangedFilesAggreegates(self):
    """Test that ``AggregateChangedFiles`` does aggregate reasons per file.

    In the main/inner loop of ``AggregateChangedFiles``: if multiple
    features all blame the same file change, we try to aggregate those
    reasons so that we only report the file once (with all reasons). None
    of the other tests here actually check the case where the same file
    is blamed multiple times, so we check that here.

    In particular, we provide the same ``FeatureValue`` twice, and
    hence the same ``ChangedFile`` twice; so we should get back a single
    ``ChangedFile`` but with the ``reasons`` fields concatenated.
    """
    file_reason = 'I blame you!'
    file_blame = ChangedFile(
        name = 'a.cc',
        blame_url = None,
        reasons = [file_reason]
    )

    feature_value = FeatureValue(
        name = 'dummy feature',
        value = 42,
        reason = 'dummy reason',
        changed_files = [file_blame]
    )

    expected_file_blame = file_blame._replace(reasons = [file_reason] * 2)

    self.assertListEqual(
        [expected_file_blame],
        self.changelist_classifier.AggregateChangedFiles(
            [feature_value] * 2))

  def testSkipAddedAndDeletedRegressionRolls(self):
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
              'GetDependency', lambda *_: {})
    dep_rolls = {
        'src/dep': DependencyRoll('src/dep1', 'https://url_dep1', None, '9'),
        'src/': DependencyRoll('src/', ('https://chromium.googlesource.com/'
                                        'chromium/src.git'), '4', '5')
    }
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
              'GetDependencyRollsDict', lambda *_: dep_rolls)

    passed_in_regression_deps_rolls = []
    def _MockGetChangeLogsForFilesGroupedByDeps(regression_deps_rolls, *_):
      passed_in_regression_deps_rolls.append(regression_deps_rolls)
      return {}, None

    self.mock(changelist_classifier, 'GetChangeLogsForFilesGroupedByDeps',
              _MockGetChangeLogsForFilesGroupedByDeps)
    self.mock(changelist_classifier, 'GetStackInfosForFilesGroupedByDeps',
              lambda *_: {})
    self.mock(changelist_classifier, 'FindSuspects', lambda *_: None)

    callstack = CallStack(0)
    self.changelist_classifier(CrashReport(crashed_version = '5',
                               signature = 'sig',
                               platform = 'canary',
                               stacktrace = Stacktrace([callstack], callstack),
                               regression_range = ['4', '5']))
    expected_regression_deps_rolls = copy.deepcopy(dep_rolls)

    # Regression of a dep added/deleted (old_revision/new_revision is None) can
    # not be known for sure and this case rarely happens, so just filter them
    # out.
    del expected_regression_deps_rolls['src/dep']
    self.assertEqual(passed_in_regression_deps_rolls[0],
                     expected_regression_deps_rolls)

  # TODO(http://crbug.com/659346): why do these mocks give coverage
  # failures? That's almost surely hiding a bug in the tests themselves.
  def testFindItForCrashNoRegressionRange(self): # pragma: no cover
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
        'GetDependencyRollsDict', lambda *_: {})
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
        'GetDependency', lambda *_: {})
    # N.B., for this one test we really do want regression_range=None.
    report = DUMMY_REPORT._replace(regression_range=None)
    self.assertListEqual(self.changelist_classifier(report), [])

  def testFindItForCrashNoMatchFound(self):
    self.mock(changelist_classifier, 'FindSuspects', lambda *_: [])
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
        'GetDependencyRollsDict',
        lambda *_: {'src/': DependencyRoll('src/', 'https://repo', '1', '2')})
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
        'GetDependency', lambda *_: {})
    self.assertListEqual(self.changelist_classifier(DUMMY_REPORT), [])

  def testFindItForCrash(self):

    def _MockFindSuspects(*_):
      suspect1 = Suspect(DUMMY_CHANGELOG1, 'src/')
      frame1 = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [1])
      frame2 = StackFrame(1, 'src/', 'func', 'a.cc', 'src/a.cc', [7])
      suspect1.file_to_stack_infos = {
          'a.cc': [StackInfo(frame1, 0), StackInfo(frame2, 0)]
      }
      suspect1.file_to_analysis_info = {
          'a.cc': AnalysisInfo(min_distance=0, min_distance_frame=frame1)
      }

      suspect2 = Suspect(DUMMY_CHANGELOG3, 'src/')
      frame3 = StackFrame(5, 'src/', 'func', 'f.cc', 'src/f.cc', [1])
      suspect2.file_to_stack_infos = {
          'f.cc': [StackInfo(frame3, 0)]
      }
      suspect2.file_to_analysis_info = {
          'a.cc': AnalysisInfo(min_distance=20, min_distance_frame=frame3)
      }

      return [suspect1, suspect2]

    self.mock(changelist_classifier, 'FindSuspects', _MockFindSuspects)
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
        'GetDependencyRollsDict',
        lambda *_: {'src/': DependencyRoll('src/', 'https://repo', '1', '2')})
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
        'GetDependency', lambda *_: {})

    suspects = self.changelist_classifier(DUMMY_REPORT)
    self.assertTrue(suspects,
        "Expected suspects, but the classifier didn't return any")

    expected_suspects = [
        {
            'review_url': 'https://codereview.chromium.org/3281',
            'url': 'https://repo.test/+/3',
            'author': 'e@chromium.org',
            'time': 'Thu Apr 1 21:24:43 2016',
            'project_path': 'src/',
            'revision': '3',
            'confidence': math.log(0.2857142857142857 * 0.6),
            'reasons': [
                ('MinDistance', math.log(0.6), 'Minimum distance is 20'),
                ('TopFrameIndex', math.log(0.2857142857142857),
                    'Top frame is #5')],
            'changed_files': [
                {
                    'file': 'a.cc',
                    'blame_url': None,
                    'info': 'Minimum distance (LOC) 20, frame #5',
                }],
        }, {
            'review_url': 'https://codereview.chromium.org/3281',
            'url': 'https://repo.test/+/1',
            'author': 'r@chromium.org',
            'time': 'Thu Mar 31 21:24:43 2016',
            'project_path': 'src/',
            'revision': '1',
            'confidence': 0.,
            'reasons': [
                ('MinDistance', 0., 'Minimum distance is 0'),
                ('TopFrameIndex', 0., 'Top frame is #0')],
            'changed_files': [
                {
                    'file': 'a.cc',
                    'blame_url': None,
                    'info': 'Minimum distance (LOC) 0, frame #0',
                }],
        },
    ]
    self.assertListEqual([suspect.ToDict() for suspect in suspects],
                         expected_suspects)

  def testFinditForCrashFilterZeroConfidenceSuspects(self):
    def _MockFindSuspects(*_):
      suspect1 = Suspect(DUMMY_CHANGELOG1, 'src/')
      frame1 = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [1])
      frame2 = StackFrame(1, 'src/', 'func', 'a.cc', 'src/a.cc', [7])
      suspect1.file_to_stack_infos = {
          'a.cc': [StackInfo(frame1, 0), StackInfo(frame2, 0)]
      }
      suspect1.file_to_analysis_info = {
          'a.cc': AnalysisInfo(min_distance=1, min_distance_frame=frame1)
      }

      suspect2 = Suspect(DUMMY_CHANGELOG3, 'src/')
      frame3 = StackFrame(15, 'src/', 'func', 'f.cc', 'src/f.cc', [1])
      suspect2.file_to_stack_infos = {
          'f.cc': [StackInfo(frame3, 0)]
      }
      suspect2.file_to_analysis_info = {
          'f.cc': AnalysisInfo(min_distance=20, min_distance_frame=frame3)
      }

      suspect3 = Suspect(DUMMY_CHANGELOG3, 'src/')
      frame4 = StackFrame(3, 'src/', 'func', 'ff.cc', 'src/ff.cc', [1])
      suspect3.file_to_stack_infos = {
          'f.cc': [StackInfo(frame4, 0)]
      }
      suspect3.file_to_analysis_info = {
          'f.cc': AnalysisInfo(min_distance=60, min_distance_frame=frame4)
      }

      return [suspect1, suspect2, suspect3]

    self.mock(changelist_classifier, 'FindSuspects', _MockFindSuspects)
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
        'GetDependencyRollsDict',
        lambda *_: {'src/': DependencyRoll('src/', 'https://repo', '1', '2')})
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
        'GetDependency', lambda *_: {})

    suspects = self.changelist_classifier(DUMMY_REPORT)
    self.assertTrue(suspects,
        "Expected suspects, but the classifier didn't return any")

    expected_suspects = [
        {
            'author': 'r@chromium.org',
            'changed_files': [
                {
                    'blame_url': None,
                    'file': 'a.cc',
                    'info': 'Minimum distance (LOC) 1, frame #0'
                }
            ],
            'confidence': math.log(0.98),
            'project_path': 'src/',
            'reasons': [
                ('MinDistance', math.log(0.98), 'Minimum distance is 1'),
                ('TopFrameIndex', 0., 'Top frame is #0'),
            ],
            'review_url': 'https://codereview.chromium.org/3281',
            'revision': '1',
            'time': 'Thu Mar 31 21:24:43 2016',
            'url': 'https://repo.test/+/1'
        },
    ]
    self.assertListEqual([suspect.ToDict() for suspect in suspects],
                         expected_suspects)

  def testFinditForCrashAllSuspectsWithZeroConfidences(self):
    """Test that we filter out suspects with too-large frame indices.

    In the mock suspects below we return frames with indices
    15, 20, 21 which are all larger than the ``max_top_n`` of
    ``TopFrameIndexFeature``. Therefore we should get a score of zero
    for that feature, which should cause the suspects to be filtered out.
    """
    def _MockFindSuspects(*_):
      suspect1 = Suspect(DUMMY_CHANGELOG1, 'src/')
      frame1 = StackFrame(20, 'src/', '', 'func', 'a.cc', [1])
      frame2 = StackFrame(21, 'src/', '', 'func', 'a.cc', [7])
      suspect1.file_to_stack_infos = {
          'a.cc': [StackInfo(frame1, 0), StackInfo(frame2, 0)]
      }
      suspect1.file_to_analysis_info = {
          'a.cc': AnalysisInfo(min_distance=1, min_distance_frame=frame1)
      }

      suspect2 = Suspect(DUMMY_CHANGELOG3, 'src/')
      frame3 = StackFrame(15, 'src/', '', 'func', 'f.cc', [1])
      suspect2.file_to_stack_infos = {
          'f.cc': [StackInfo(frame3, 0)]
      }
      suspect2.min_distance = 20
      suspect2.file_to_analysis_info = {
          'f.cc': AnalysisInfo(min_distance=20, min_distance_frame=frame3)
      }

      return [suspect1, suspect2]

    self.mock(changelist_classifier, 'FindSuspects', _MockFindSuspects)
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
        'GetDependencyRollsDict',
        lambda *_: {'src/': DependencyRoll('src/', 'https://repo', '1', '2')})
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
        'GetDependency', lambda *_: {})

    suspects = self.changelist_classifier(DUMMY_REPORT)
    self.assertFalse(suspects, 'Expected zero suspects, but found some:\n%s'
        % pprint.pformat([suspect.ToDict() for suspect in suspects]))
