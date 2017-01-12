# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash.stacktrace import StackFrame
from crash.suspect import AnalysisInfo
from crash.suspect import StackInfo
from crash.suspect import Suspect
from crash.suspect import SuspectMap
from crash.test.crash_test_suite import CrashTestSuite
from libs.gitiles.blame import Blame
from libs.gitiles.blame import Region
from libs.gitiles.change_log import ChangeLog

DUMMY_CHANGELOG1 = ChangeLog.FromDict({
    'author': {
        'name': 'r@chromium.org',
        'email': 'r@chromium.org',
        'time': 'Thu Mar 31 21:24:43 2016',
    },
    'committer': {
        'email': 'r',
        'time': 'Thu Mar 31 21:28:39 2016',
        'name': 'example@chromium.org',
    },
    'message': 'dummy',
    'commit_position': 175900,
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
    'commit_url':
        'https://repo.test/+/1',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'revision': '1',
    'reverted_revision': None
})

DUMMY_CHANGELOG2 = ChangeLog.FromDict({
    'author': {
        'name': 'e@chromium.org',
        'email': 'e@chromium.org',
        'time': 'Thu Mar 31 21:24:43 2016',
    },
    'committer': {
        'name': 'e',
        'email': 'e@chromium.org',
        'time': 'Thu Mar 31 21:28:39 2016',
    },
    'message': 'dummy',
    'commit_position': 175911,
    'touched_files': [
        {
            'change_type': 'modify',
            'new_path': 'a.cc',
            'old_path': 'a.cc',
        },
    ],
    'commit_url':
        'https://repo.test/+/2',
    'code_review_url': 'https://codereview.chromium.org/3290',
    'revision': '2',
    'reverted_revision': None
})

DUMMY_BLAME = Blame('4', 'a.cc')
DUMMY_BLAME.AddRegions([
    Region(1, 5, '2', 'r', 'r@chromium.org', 'Thu Mar 25 21:24:43 2016'),
    Region(6, 3, '1', 'e', 'e@chromium.org', 'Thu Mar 31 21:24:43 2016'),
    Region(9, 2, '3', 'k', 'k@chromium.org', 'Thu Apr 1 21:24:43 2016')])

DUMMY_BLAME2 = Blame('4', 'b.cc')
DUMMY_BLAME2.AddRegions([
    Region(1, 5, '2', 'r', 'r@chromium.org', 'Thu Mar 25 21:24:43 2016'),
    Region(6, 3, '1', 'e', 'e@chromium.org', 'Thu Mar 31 21:24:43 2016')])


class SuspectTest(CrashTestSuite):

  def testSuspectToDict(self):

    suspect = Suspect(DUMMY_CHANGELOG1, 'src/',
                      confidence=1, reasons=['MinDistance', 0.5, 'some reason'],
                      changed_files={'file': 'f', 'blame_url': 'http://b',
                                     'info': 'min distance (LOC) 5'})

    expected_suspect_json = {
        'url': DUMMY_CHANGELOG1.commit_url,
        'review_url': DUMMY_CHANGELOG1.code_review_url,
        'revision': DUMMY_CHANGELOG1.revision,
        'project_path': 'src/',
        'author': DUMMY_CHANGELOG1.author.email,
        'time': str(DUMMY_CHANGELOG1.author.time),
        'reasons': ['MinDistance', 0.5, 'some reason'],
        'changed_files': {'file': 'f', 'blame_url': 'http://b',
                          'info': 'min distance (LOC) 5'},
        'confidence': 1,
    }

    self.assertEqual(suspect.ToDict(), expected_suspect_json)

  def testSuspectToString(self):

    suspect = Suspect(DUMMY_CHANGELOG1, 'src/', confidence=1)

    expected_str = ''
    self.assertEqual(suspect.ToString(), expected_str)

    suspect.file_to_stack_infos = {
        'a.cc': [StackInfo(
            frame = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', []),
            priority = 0)]
    }
    expected_str = 'Changed file a.cc crashed in frame #0'

    self.assertEqual(str(suspect), expected_str)

  def testSuspectUpdate(self):
    # Touched lines have intersection with crashed lines.
    suspect = Suspect(DUMMY_CHANGELOG1, 'src/', confidence=1)
    stack_infos = [StackInfo(
        frame = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [7]),
        priority = 0)]

    suspect._UpdateSuspect('a.cc', stack_infos, DUMMY_BLAME)
    self.assertEqual(suspect.file_to_analysis_info['a.cc'].min_distance, 0)

    # Touched lines are before crashed lines.
    suspect = Suspect(DUMMY_CHANGELOG1, 'src/', confidence=1)

    stack_infos = [StackInfo(
        frame = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [3]),
        priority = 0)]

    suspect._UpdateSuspect('a.cc', stack_infos, DUMMY_BLAME)
    self.assertEqual(suspect.file_to_analysis_info['a.cc'].min_distance, 3)

    # Touched lines are after crashed lines.
    suspect = Suspect(DUMMY_CHANGELOG1, 'src/', confidence=1)

    stack_infos = [StackInfo(
        frame = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [10]),
        priority = 0)]

    suspect._UpdateSuspect('a.cc', stack_infos, DUMMY_BLAME)
    self.assertEqual(suspect.file_to_analysis_info['a.cc'].min_distance, 2)

  def testSuspectUpdateWithEmptyBlame(self):
    suspect = Suspect(DUMMY_CHANGELOG1, 'src/', confidence=1)
    stack_infos = [StackInfo(
        frame = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [7]),
        priority = 0)]

    suspect._UpdateSuspect('a.cc', stack_infos, None)
    self.assertEqual(suspect.file_to_stack_infos['a.cc'], stack_infos)
    self.assertEqual(suspect.file_to_analysis_info, {})

  def testSuspectUpdateMinimumDistance(self):
    suspect = Suspect(DUMMY_CHANGELOG1, 'src/', confidence=1)
    frame1 = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [7])
    frame2 = StackFrame(2, 'src/', 'func', 'a.cc', 'src/a.cc', [20])
    stack_infos = [StackInfo(frame1, 0), StackInfo(frame2, 0)]

    suspect._UpdateSuspect('a.cc', stack_infos, DUMMY_BLAME)
    self.assertEqual(suspect.file_to_stack_infos['a.cc'], stack_infos)
    self.assertEqual(suspect.file_to_analysis_info,
        {'a.cc': AnalysisInfo(min_distance = 0, min_distance_frame = frame1)})

  def testSuspectsGenerateSuspects(self):
    suspects = SuspectMap(ignore_cls=set(['2']))
    frame1 = StackFrame(0, 'src/',  'func', 'a.cc', 'src/a.cc', [7])
    frame2 = StackFrame(1, 'src/',  'func', 'b.cc', 'src/b.cc', [11])
    stack_infos1 = [StackInfo(frame1, 0)]
    stack_infos2 = [StackInfo(frame2, 0)]
    suspects.GenerateSuspects('a.cc', 'src/', stack_infos1,
                                       [DUMMY_CHANGELOG1, DUMMY_CHANGELOG2],
                                       DUMMY_BLAME)

    suspects.GenerateSuspects('b.cc', 'src/', stack_infos2,
                                       [DUMMY_CHANGELOG1, DUMMY_CHANGELOG2],
                                       DUMMY_BLAME2)

    expected_suspect = Suspect(DUMMY_CHANGELOG1, 'src/')
    expected_suspect.file_to_stack_infos = {
        'a.cc': stack_infos1,
        'b.cc': stack_infos2,
    }
    expected_suspect.file_to_analysis_info = {
        'a.cc': AnalysisInfo(min_distance = 0, min_distance_frame = frame1),
        'b.cc': AnalysisInfo(min_distance = 3, min_distance_frame = frame2),
    }

    expected_suspects = SuspectMap(ignore_cls=set(['2']))
    expected_suspects['1'] = expected_suspect

    self._VerifyTwoSuspectMapEqual(suspects, expected_suspects)
