# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from analysis.project import Project
from analysis.stacktrace import StackFrame
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.diff import ChangeType


class ProjectTest(unittest.TestCase):
  """Tests ``Project`` class."""

  def setUp(self):
    super(ProjectTest, self).setUp()
    self.android_project = Project('android_os',
                                   path_regexes=['.*googleplex-android/'],
                                   function_regexes=['android.'])
    self.chromium_project = Project('chromium',
                                    function_regexes=['org.chromium'],
                                    host_directories=['src/'])

  def testMatchesStackFrame(self):
    """Tests that ``MatchesStackFrame`` matches frames."""
    chromium_frame = StackFrame(0, 'src/', 'func', 'f.cc', 'src/f.cc', [2])
    self.assertTrue(self.chromium_project.MatchesStackFrame(chromium_frame))
    self.assertFalse(self.android_project.MatchesStackFrame(chromium_frame))

    android_frame1 = StackFrame(0, '', 'android.a', 'comp1.cc',
                                'src/comp1.cc', [2])
    self.assertFalse(self.chromium_project.MatchesStackFrame(android_frame1))
    self.assertTrue(self.android_project.MatchesStackFrame(android_frame1))

    android_frame2 = StackFrame(0, '', 'func', 'comp2.cc',
                               'googleplex-android/src/comp2.cc', [32])
    self.assertFalse(self.chromium_project.MatchesStackFrame(android_frame2))
    self.assertTrue(self.android_project.MatchesStackFrame(android_frame2))

  def testMatchesTouchedFile(self):
    """Tests that ``MatchesTouchedFile`` matches touched files correctly."""
    touched_file = FileChangeInfo(ChangeType.MODIFY, 'a/b.h', 'a/b.h')
    self.assertFalse(self.chromium_project.MatchesTouchedFile(
        'dummy', touched_file.changed_path))
    self.assertTrue(self.chromium_project.MatchesTouchedFile(
        'src/', touched_file.changed_path))

    deleted_file = FileChangeInfo(ChangeType.DELETE, 'a/b.h', None)
    self.assertTrue(self.chromium_project.MatchesTouchedFile(
        'src/', deleted_file.changed_path))
    self.assertFalse(self.android_project.MatchesTouchedFile(
        'src/', deleted_file.changed_path))

    add_file = FileChangeInfo(ChangeType.ADD, None, 'googleplex-android/b.java')
    self.assertTrue(self.android_project.MatchesTouchedFile(
        'android_path/', add_file.changed_path))

  def testGetName(self):
    """Tests ``GetName`` method return the project or subproject name."""
    self.assertEquals(self.android_project.GetName(), self.android_project.name)
    self.assertEquals(self.chromium_project.GetName(),
                      self.chromium_project.name)
    self.assertEquals(self.chromium_project.GetName('src/'), 'chromium')
    self.assertEquals(self.chromium_project.GetName('src/dep'), 'chromium-dep')
    self.assertEquals(self.chromium_project.GetName('dummy/dep'),
                      'chromium-dummy_dep')
