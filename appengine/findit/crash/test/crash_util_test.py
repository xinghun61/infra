# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple

from crash import crash_util
from crash.crash_match import CrashMatch
from crash.crash_match import FrameInfo
from crash.stacktrace import CallStack
from crash.stacktrace import StackFrame
from crash.stacktrace import Stacktrace
from crash.suspect import Suspect
from crash.test.predator_testcase import PredatorTestCase
from libs.deps.dependency import Dependency
from libs.gitiles.change_log import ChangeLog

_CHANGELOG = ChangeLog.FromDict({
    'author': {
        'name': 'r@chromium.org',
        'email': 'r@chromium.org',
        'time': 'Thu Mar 31 21:24:43 2016',
    },
    'committer': {
        'name': 'example@chromium.org',
        'email': 'r@chromium.org',
        'time': 'Thu Mar 31 21:28:39 2016',
    },
    'message': 'dummy',
    'commit_position': 175900,
    'touched_files': [
        {
            'change_type': 'modify',
            'new_path': 'src/a.cc',
            'old_path': 'src/a.cc',
        },
    ],
    'commit_url':
        'https://repo.test/+/1',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'revision': '1',
    'reverted_revision': None
})


def Factory(frame):
  return MockCrashedGroup(frame.raw_file_path) if frame.raw_file_path else None


def Match(crashed, touched_file):
  return touched_file.new_path == crashed.value


class MockCrashedGroup(namedtuple('MockCrashedGroup', ['value'])):

  __slots__ = ()



class CrashUtilTest(PredatorTestCase):

  def testIsSameFilePath(self):
    path_1 = 'third_party/a/b/c/file.cc'
    path_2 = 'third_party/a/file.cc'

    self.assertTrue(crash_util.IsSameFilePath(path_1, path_2))

    path_1 = 'a/b/c/file.cc'
    path_2 = 'a/b/c/file2.cc'

    self.assertFalse(crash_util.IsSameFilePath(path_1, path_2))

    path_1 = 'a/b/c/d/e/file.cc'
    path_2 = 'f/g/file.cc'

    self.assertTrue(crash_util.IsSameFilePath(None, None))
    self.assertFalse(crash_util.IsSameFilePath(path_1, path_2))
    self.assertFalse(crash_util.IsSameFilePath(None, path_2))
    self.assertFalse(crash_util.IsSameFilePath(path_1, None))

  def testIndexFramesWithCrashedGroup(self):
    """Tests ``IndexFramesWithCrashedGroup`` function."""
    frame1 = StackFrame(0, 'src/', 'func', 'f.cc',
                        'src/f.cc', [2, 3], 'h://repo')
    frame2 = StackFrame(1, 'src/', 'func', 'a.cc',
                        'src/a.cc', [31, 32], 'h://repo')
    frame3 = StackFrame(1, 'src/dummy', 'func', 'a.cc',
                        'src/dummy/a.cc', [131, 132], 'h://repo')
    stack = CallStack(0, frame_list=[frame1, frame2, frame3])
    stack_trace = Stacktrace([stack], stack)
    deps = {'src/': Dependency('src/', 'h://repo', 'rev3')}

    indexed_frame_infos = crash_util.IndexFramesWithCrashedGroup(
        stack_trace, Factory, deps)
    expected_frame_infos = {'src/': {MockCrashedGroup('src/f.cc'):
                                     [FrameInfo(frame1, 0)],
                                     MockCrashedGroup('src/a.cc'):
                                     [FrameInfo(frame2, 0)]}}
    self.assertEqual(indexed_frame_infos, expected_frame_infos)

  def testDoNotIndexFramesWithNoneCrashedGroup(self):
    """Tests ``IndexFramesWithCrashedGroup`` function."""
    frame = StackFrame(0, 'src/', 'func', '', '', [2], 'h://repo')
    stack = CallStack(0, frame_list=[frame])
    stack_trace = Stacktrace([stack], stack)
    deps = {'src/': Dependency('src/', 'h://repo', 'rev3')}

    indexed_frame_infos = crash_util.IndexFramesWithCrashedGroup(
        stack_trace, Factory, deps)
    self.assertEqual(indexed_frame_infos, {})

  def testMatchSuspectWithFrameInfos(self):
    """Tests ``MatchSuspectWithFrameInfos`` function."""
    frame1 = StackFrame(0, 'src/', 'func', 'f.cc',
                        'src/f.cc', [2, 3], 'h://repo')
    frame2 = StackFrame(1, 'src/', 'func', 'a.cc',
                        'src/a.cc', [31, 32], 'h://repo')
    grouped_frame_infos = {
        MockCrashedGroup('src/f.cc'): [FrameInfo(frame1, 0)],
        MockCrashedGroup('src/a.cc'): [FrameInfo(frame2, 0)]
    }
    suspect = Suspect(_CHANGELOG, 'src/')
    matches = crash_util.MatchSuspectWithFrameInfos(suspect,
                                                    grouped_frame_infos,
                                                    Match)
    crashed = MockCrashedGroup('src/a.cc')
    expected_matches = {
        crashed: CrashMatch(crashed, _CHANGELOG.touched_files,
                            [FrameInfo(frame2, 0)])
    }
    self.assertDictEqual(matches, expected_matches)
