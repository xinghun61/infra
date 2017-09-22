# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.analysis_testcase import AnalysisTestCase
from analysis.stacktrace import StackFrame
from analysis.stacktrace import CallStack
from analysis.project import Project
from analysis.project_classifier import ProjectClassifier
from analysis.suspect import Suspect
from analysis.type_enums import LanguageType
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.diff import ChangeType


PROJECT_CONFIG = {
    'project_path_function_hosts': [
        ['android_os', ['googleplex-android/'], ['android.'], None],
        ['chromium', None, ['org.chromium'], ['src']]
    ],
    'non_chromium_project_rank_priority': {
        'android_os': '-1',
        'others': '-2',
    },
    'top_n': 4
}


class ProjectClassifierTest(AnalysisTestCase):
  """Tests ``ProjectClassifier`` class."""

  def setUp(self):
    super(ProjectClassifierTest, self).setUp()
    projects = [Project(name, path_regexs, function_regexs, host_directories)
                for name, path_regexs, function_regexs, host_directories
                in PROJECT_CONFIG['project_path_function_hosts']]
    self.classifier = ProjectClassifier(
        projects, PROJECT_CONFIG['top_n'],
        PROJECT_CONFIG['non_chromium_project_rank_priority'])

  def testClassifyCallStack(self):
    """Tests ``ClassifyCallStack`` method."""
    callstack = CallStack(
        0, [StackFrame(0, 'src', 'func', 'f.cc', 'src/f.cc', [2])])
    self.assertEqual(
        self.classifier.ClassifyCallStack(callstack), 'chromium')

    callstack = CallStack(
        0, [StackFrame(0, '', 'android.a', 'comp1.cc', 'src/comp1.cc', [2])])
    self.assertEqual(
        self.classifier.ClassifyCallStack(callstack), 'android_os')

    callstack = CallStack(
        0, [StackFrame(0, '', 'func', 'comp2.cc',
                       'googleplex-android/src/comp2.cc', [32])])
    self.assertEqual(
        self.classifier.ClassifyCallStack(callstack), 'android_os')

    callstack = CallStack(
        0, [StackFrame(0, '', 'func', 'comp2.cc', 'unknown/comp2.cc', [32])])
    self.assertIsNone(self.classifier.ClassifyCallStack(callstack))

    callstack = CallStack(
        0, [StackFrame(0, '', 'android.a.b', 'f.java', 'unknown/f.java', [32])],
        language_type=LanguageType.JAVA)
    self.assertEqual(
        self.classifier.ClassifyCallStack(callstack), 'android_os')

  def testClassifyJavaCallstack(self):
    """Tests ``ClassifyCallStack`` classify java callstack."""
    callstack = CallStack(
        0, [StackFrame(0, 'src', 'org.chromium.ab',
                       'f.java', 'unknown/f.java', [32])],
        language_type=LanguageType.JAVA)
    self.assertEqual(
        self.classifier.ClassifyCallStack(callstack), 'chromium')

  def testClassifySuspect(self):
    """Tests ``ClassifySuspect`` method."""
    suspect = Suspect(self.GetDummyChangeLog(), 'src')
    self.assertEqual(self.classifier.ClassifySuspect(suspect), 'chromium')

  def testClassifyEmptySuspect(self):
    """Tests ``ClassifySuspect`` returns None for empty suspect."""
    self.assertIsNone(self.classifier.ClassifySuspect(None))

  def testClassifySuspectNoTouchedFileMatch(self):
    """Tests ``ClassifySuspect`` returns None if there is no file match."""
    suspect = Suspect(self.GetDummyChangeLog(), 'dummy')
    suspect.touched_files = [FileChangeInfo(ChangeType.MODIFY,
                                            'a/b.h', 'a/b.h')]
    self.assertIsNone(self.classifier.ClassifySuspect(suspect))

  def testClassifySuspects(self):
    """Tests ``ClassifySuspects`` classify a list of ``Suspect``s."""
    suspect1 = Suspect(self.GetDummyChangeLog(), 'src')
    suspect2 = Suspect(self.GetDummyChangeLog(), 'src/dep')
    suspect3 = Suspect(self.GetDummyChangeLog(), 'src/dep')

    self.assertEqual(self.classifier.ClassifySuspects(
        [suspect1, suspect2, suspect3]), 'chromium-dep')
