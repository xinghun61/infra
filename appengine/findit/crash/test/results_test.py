# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.blame import Region
from common.blame import Blame
from common.change_log import ChangeLog
from crash.stacktrace import StackFrame
from crash.results import AnalysisInfo
from crash.results import Result
from crash.results import MatchResult
from crash.results import MatchResults
from crash.test.crash_test_suite import CrashTestSuite

DUMMY_CHANGELOG1 = ChangeLog.FromDict({
    'author_name': 'r@chromium.org',
    'message': 'dummy',
    'committer_email': 'r@chromium.org',
    'commit_position': 175900,
    'author_email': 'r@chromium.org',
    'touched_files': [
        {
            'change_type': 'modify',
            'new_path': 'a.cc',
            'old_path': 'a.cc',
        },
        {
            'change_type': 'modify',
            'new_path': 'b.cc',
            'old_path': 'b.cc',
        },
    ],
    'author_time': 'Thu Mar 31 21:24:43 2016',
    'committer_time': 'Thu Mar 31 21:28:39 2016',
    'commit_url':
        'https://repo.test/+/1',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'committer_name': 'r',
    'revision': '1',
    'reverted_revision': None
})

DUMMY_CHANGELOG2 = ChangeLog.FromDict({
    'author_name': 'e@chromium.org',
    'message': 'dummy',
    'committer_email': 'e@chromium.org',
    'commit_position': 175911,
    'author_email': 'e@chromium.org',
    'touched_files': [
        {
            'change_type': 'modify',
            'new_path': 'a.cc',
            'old_path': 'a.cc',
        },
    ],
    'author_time': 'Thu Mar 31 21:24:43 2016',
    'committer_time': 'Thu Mar 31 21:28:39 2016',
    'commit_url':
        'https://repo.test/+/2',
    'code_review_url': 'https://codereview.chromium.org/3290',
    'committer_name': 'e',
    'revision': '2',
    'reverted_revision': None
})

DUMMY_BLAME = Blame('4', 'a.cc')
DUMMY_BLAME.AddRegion(
    Region(1, 5, '2', 'r', 'r@chromium.org', 'Thu Mar 25 21:24:43 2016'))
DUMMY_BLAME.AddRegion(
    Region(6, 3, '1', 'e', 'e@chromium.org', 'Thu Mar 31 21:24:43 2016'))
DUMMY_BLAME.AddRegion(
    Region(9, 2, '3', 'k', 'k@chromium.org', 'Thu Apr 1 21:24:43 2016'))

DUMMY_BLAME2 = Blame('4', 'b.cc')
DUMMY_BLAME2.AddRegion(
    Region(1, 5, '2', 'r', 'r@chromium.org', 'Thu Mar 25 21:24:43 2016'))
DUMMY_BLAME2.AddRegion(
    Region(6, 3, '1', 'e', 'e@chromium.org', 'Thu Mar 31 21:24:43 2016'))


class ResultsTest(CrashTestSuite):

  def testResultToDict(self):

    result = Result(DUMMY_CHANGELOG1, 'src/',
                    confidence=1, reasons=['MinDistance', 0.5, 'some reason'],
                    changed_files={'file': 'f', 'blame_url': 'http://b',
                                   'info': 'min distance (LOC) 5'})

    expected_result_json = {
        'url': DUMMY_CHANGELOG1.commit_url,
        'review_url': DUMMY_CHANGELOG1.code_review_url,
        'revision': DUMMY_CHANGELOG1.revision,
        'project_path': 'src/',
        'author': DUMMY_CHANGELOG1.author_email,
        'time': str(DUMMY_CHANGELOG1.author_time),
        'reasons': ['MinDistance', 0.5, 'some reason'],
        'changed_files': {'file': 'f', 'blame_url': 'http://b',
                          'info': 'min distance (LOC) 5'},
        'confidence': 1,
    }

    self.assertEqual(result.ToDict(), expected_result_json)

  def testResultToString(self):

    result = Result(DUMMY_CHANGELOG1, 'src/', confidence=1)

    expected_result_str = ''
    self.assertEqual(result.ToString(), expected_result_str)

    result.file_to_stack_infos = {
        'a.cc': [(StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', []), 0)]
    }
    expected_result_str = 'Changed file a.cc crashed in frame #0'

    self.assertEqual(str(result), expected_result_str)

  def testMatchResultUpdate(self):
    # Touched lines have intersection with crashed lines.
    result = MatchResult(DUMMY_CHANGELOG1, 'src/', confidence=1)
    stack_infos = [(StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [7]), 0)]

    result.Update('a.cc', stack_infos, DUMMY_BLAME)
    self.assertEqual(result.file_to_analysis_info['a.cc'].min_distance, 0)

    # Touched lines are before crashed lines.
    result = MatchResult(DUMMY_CHANGELOG1, 'src/', confidence=1)

    stack_infos = [(StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [3]), 0)]

    result.Update('a.cc', stack_infos, DUMMY_BLAME)
    self.assertEqual(result.file_to_analysis_info['a.cc'].min_distance, 3)

    # Touched lines are after crashed lines.
    result = MatchResult(DUMMY_CHANGELOG1, 'src/', confidence=1)

    stack_infos = [(StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [10]), 0)]

    result.Update('a.cc', stack_infos, DUMMY_BLAME)
    self.assertEqual(result.file_to_analysis_info['a.cc'].min_distance, 2)

  def testMatchResultUpdateWithEmptyBlame(self):
    result = MatchResult(DUMMY_CHANGELOG1, 'src/', confidence=1)
    stack_infos = [(StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [7]), 0)]

    result.Update('a.cc', stack_infos, None)
    self.assertEqual(result.file_to_stack_infos['a.cc'], stack_infos)
    self.assertEqual(result.file_to_analysis_info, {})

  def testMatchResultUpdateMinimumDistance(self):
    result = MatchResult(DUMMY_CHANGELOG1, 'src/', confidence=1)
    frame1 = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [7])
    frame2 = StackFrame(2, 'src/', 'func', 'a.cc', 'src/a.cc', [20])
    stack_infos = [(frame1, 0), (frame2, 0)]

    result.Update('a.cc', stack_infos, DUMMY_BLAME)
    self.assertEqual(result.file_to_stack_infos['a.cc'], stack_infos)
    self.assertEqual(result.file_to_analysis_info,
        {'a.cc': AnalysisInfo(min_distance = 0, min_distance_frame = frame1)})

  def testMatchResultsGenerateMatchResults(self):
    match_results = MatchResults(ignore_cls=set(['2']))
    frame1 = StackFrame(0, 'src/',  'func', 'a.cc', 'src/a.cc', [7])
    frame2 = StackFrame(1, 'src/',  'func', 'b.cc', 'src/b.cc', [11])
    stack_infos1 = [(frame1, 0)]
    stack_infos2 = [(frame2, 0)]
    match_results.GenerateMatchResults('a.cc', 'src/', stack_infos1,
                                       [DUMMY_CHANGELOG1, DUMMY_CHANGELOG2],
                                       DUMMY_BLAME)

    match_results.GenerateMatchResults('b.cc', 'src/', stack_infos2,
                                       [DUMMY_CHANGELOG1, DUMMY_CHANGELOG2],
                                       DUMMY_BLAME2)

    expected_match_result = MatchResult(DUMMY_CHANGELOG1, 'src/')
    expected_match_result.file_to_stack_infos = {
        'a.cc': stack_infos1,
        'b.cc': stack_infos2,
    }
    expected_match_result.file_to_analysis_info = {
        'a.cc': AnalysisInfo(min_distance = 0, min_distance_frame = frame1),
        'b.cc': AnalysisInfo(min_distance = 3, min_distance_frame = frame2),
    }

    expected_match_results = MatchResults(ignore_cls=set(['2']))
    expected_match_results['1'] = expected_match_result

    self._VerifyTwoMatchResultsEqual(match_results, expected_match_results)
