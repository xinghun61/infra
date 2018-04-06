# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple

from analysis import crash_util
from analysis.analysis_testcase import AnalysisTestCase
from analysis.crash_match import CrashMatch
from analysis.crash_match import FrameInfo
from analysis.stacktrace import CallStack
from analysis.stacktrace import ProfilerStackFrame
from analysis.stacktrace import StackFrame
from analysis.stacktrace import Stacktrace
from analysis.suspect import Suspect
from analysis.type_enums import RenameType
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



class CrashUtilTest(AnalysisTestCase):

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

  def testIndexFramesWithCrashedGroupWhenFrameHasNoDepPath(self):
    """Tests a bug with ``IndexFramesWithCrashedGroup``.

    This function would crash when passed a frame with a ``None`` dep path.
    Instead it should ignore this frame.
    """
    frame = ProfilerStackFrame(0, 0.1, 0.5, True, dep_path=None)
    stack = CallStack(0, frame_list=[frame])
    stack_trace = Stacktrace([stack], stack)
    deps = {'src': Dependency('src', 'h://repo', 'rev3')}

    indexed_frame_infos = crash_util.IndexFramesWithCrashedGroup(
        stack_trace, Factory, deps)
    self.assertDictEqual(indexed_frame_infos, {})

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

  def testFilterStackFrameFunction(self):
    """Tests ``FilterStackFrameFunction`` strips part correctly."""
    a = 'function::(anonymous namespace)::abc'
    self.assertEqual(crash_util.FilterStackFrameFunction(a), 'function::abc')

    b = 'abc(dcew(wqn{ew}io)eqs)::penc(senc)'
    self.assertEqual(crash_util.FilterStackFrameFunction(b), 'abc')

    c = 'no_parenthese'
    self.assertEqual(crash_util.FilterStackFrameFunction(c), c)

  def testRenameFileName(self):
    """Tests ``RenameFileName`` function."""
    self.assertEqual (
        crash_util.RenameFileName('UpperFileName.cpp',
                                  RenameType.CAPITAL_TO_UNDERSCORE),
        'upper_file_name.cpp')

    self.assertEqual (
        crash_util.RenameFileName('AbcAbcAbc.cpp',
                                  RenameType.CAPITAL_TO_UNDERSCORE),
        'abc_abc_abc.cpp')

    self.assertEqual (
        crash_util.RenameFileName('underscore_file_name.cpp',
                                  RenameType.UNDERSCORE_TO_CAPITAL),
        'UnderscoreFileName.cpp')

    self.assertEqual (
        crash_util.RenameFileName('UpperFileName.cpp', None),
        'UpperFileName.cpp')

  def testMapPath(self):
    self.assertEqual(crash_util.MapPath('', []), '')
    self.assertEqual(crash_util.MapPath(None, []), None)

    change_naming_convention = crash_util.ChangeNamingConvention({'a/old_dir':
                                                     'capital_to_underscore'})
    replace_path = crash_util.ReplacePath({'a/old_dir': 'b/new_dir'})
    self.assertEqual(
        crash_util.MapPath('a/old_dir/ClassName.cpp',
                           [change_naming_convention, replace_path]),
        'b/new_dir/class_name.cpp'
    )


class ChangeNamingConventionTest(AnalysisTestCase):

  def testCall(self):
    change_naming_convention = crash_util.ChangeNamingConvention(
        {'a/b': 'capital_to_underscore'})
    self.assertEqual(change_naming_convention('a/b/ClassBlaBla.cpp'),
                     'a/b/class_bla_bla.cpp')
    self.assertEqual(change_naming_convention('a/ClassBlaBla.cpp'),
                     'a/ClassBlaBla.cpp')


class ReplacePathTest(AnalysisTestCase):

  def testCall(self):
    replace_path = crash_util.ReplacePath({'a/old_dir': 'b/new_dir'})
    self.assertEqual(replace_path('a/old_dir/ClassBlaBla.cpp'),
                                  'b/new_dir/ClassBlaBla.cpp')
    self.assertEqual(replace_path('a/ClassBlaBla.cpp'), 'a/ClassBlaBla.cpp')


class ChangeFileExtension(AnalysisTestCase):

  def testCall(self):
    change_file_extension = crash_util.ChangeFileExtension(
        {'a/b': {'cpp': 'cc'}})
    self.assertEqual(change_file_extension('a/b/ClassBlaBla.cpp'),
                                           'a/b/ClassBlaBla.cc')

    self.assertEqual(change_file_extension('a/ClassBlaBla.cpp'),
                                           'a/ClassBlaBla.cpp')
    self.assertEqual(change_file_extension('a/b/ClassBlaBla'),
                                           'a/b/ClassBlaBla')
