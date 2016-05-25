# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash.callstack import StackFrame, CallStack
from crash.project_classifier import ProjectClassifier
from crash.results import Result
from crash.test.crash_testcase import CrashTestCase
from crash.type_enums import CallStackLanguageType
from model.crash.crash_config import CrashConfig


class ProjectClassifierTest(CrashTestCase):

  def testGetProjectNameFromDepPath(self):
    classifier = ProjectClassifier()
    self.assertEqual(classifier._GetProjectFromDepPath('src/'),
                     'chromium')

    self.assertEqual(classifier._GetProjectFromDepPath('src/abc'),
                     'chromium-abc')

    self.assertEqual(classifier._GetProjectFromDepPath('unknown/unknown'),
                     'chromium-unknown_unknown')

  def testGetClassFromStackFrame(self):
    classifier = ProjectClassifier()

    frame = StackFrame(0, 'src/', 'func', 'f.cc', 'src/f.cc', [2])
    self.assertEqual(
        classifier.GetClassFromStackFrame(frame), 'chromium')

    frame = StackFrame(0, '', 'android.a', 'comp1.cc', 'src/comp1.cc', [2])
    self.assertEqual(
        classifier.GetClassFromStackFrame(frame), 'android_os')

    frame = StackFrame(0, '', 'func', 'comp2.cc',
                       'googleplex-android/src/comp2.cc', [32])
    self.assertEqual(
        classifier.GetClassFromStackFrame(frame), 'android_os')

    frame = StackFrame(0, '', 'func', 'comp2.cc', 'unknown/comp2.cc', [32])
    self.assertEqual(
        classifier.GetClassFromStackFrame(frame), '')

  def testGetClassFromResult(self):
    classifier = ProjectClassifier()

    result = Result(self.GetDummyChangeLog(), 'src/')
    result.file_to_stack_infos = {'a.cc': [(
        StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [3]), 0
    )]}
    self.assertEqual(classifier.GetClassFromResult(result), 'chromium')

    result.file_to_stack_infos = {
        'comp1.cc': [
            (StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]), 0)
        ]
    }
    self.assertEqual(classifier.GetClassFromResult(result), 'chromium')

  def testClassifyCrashStack(self):
    classifier = ProjectClassifier()

    crash_stack = CallStack(0)
    crash_stack.extend([
        StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]),
        StackFrame(1, 'src/', 'ff', 'comp1.cc', 'src/comp1.cc', [21]),
        StackFrame(2, 'src/', 'func2', 'comp2.cc', 'src/comp2.cc', [8])
    ])

    self.assertEqual(classifier.Classify([], crash_stack), 'chromium')

  def testClassifyResultsEmpty(self):
    classifier = ProjectClassifier()

    result = Result(self.GetDummyChangeLog(), '')
    self.assertEqual(classifier.Classify([result], CallStack(0)),
                     '')

  def testClassifyRankFunction(self):
    classifier = ProjectClassifier()

    result1 = Result(self.GetDummyChangeLog(), 'src/')
    result1.file_to_stack_infos = {
        'comp1.cc': [
            (StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]), 0)
        ]
    }

    self.assertEqual(classifier.Classify([result1], CallStack(0)), 'chromium')

    result2 = Result(self.GetDummyChangeLog(), '')
    result2.file_to_stack_infos = {
        'ad.cc': [
            (StackFrame(0, '', 'android.a', 'ad.cc', 'ad.cc', [2]), 0)
        ]
    }

    self.assertEqual(classifier.Classify([result2], CallStack(0)),
                     'android_os')

    self.assertEqual(classifier.Classify([result1, result2], CallStack(0)),
                     'chromium')

  def testClassifyForJavaRankFunction(self):
    classifier = ProjectClassifier()

    crash_stack = CallStack(0)
    crash_stack.language_type = CallStackLanguageType.JAVA

    crash_stack.extend([
        StackFrame(0, '', 'android.a.f', 'android/a/cc',
                   'android/a.java', [2]),
        StackFrame(1, '', 'org.chromium.c', 'org/chromium/c.java',
                   'org/chromium/c.java', [8])
    ])

    self.assertEqual(classifier.Classify([], crash_stack),
                     'chromium')

  def testClassifyReturnsNone(self):
    def _MockClassify(*_, **args):
      self.assertIsNotNone(args)
      return None

    self.mock(ProjectClassifier, '_Classify', _MockClassify)

    classifier = ProjectClassifier()
    self.assertEqual(classifier.Classify([], CallStack(0)),
                     '')

  def testProjectClassifierDoNotHaveConfig(self):
    crash_config = CrashConfig.Get()
    crash_config.project_classifier = {}
    crash_config.put()

    crash_stack = CallStack(0)
    crash_stack.extend([
        StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]),
        StackFrame(1, 'src/', 'ff', 'comp1.cc', 'src/comp1.cc', [21]),
        StackFrame(2, 'src/', 'func2', 'comp2.cc', 'src/comp2.cc', [8])
    ])

    result1 = Result(self.GetDummyChangeLog(), 'src/')
    result1.file_to_stack_infos = {
        'comp1.cc': [
            (StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]), 0)
        ]
    }

    self.assertEqual(ProjectClassifier().Classify([result1], crash_stack), '')

  def testSortHosts(self):
    host_list = [
        'src/',
        'src/chrome/browser/resources/',
        'src/media/',
        'src/sdch/',
        'src/testing/',
        'src/third_party/WebKit/',
        'src/third_party/',
        'src/tools/',
        'src/chrome/test/data/layout_tests/'
    ]

    crash_config = CrashConfig.Get()
    crash_config.project_classifier['host_directories'] = host_list

    expected_sorted_host_list = [
        'src/chrome/test/data/layout_tests/',
        'src/chrome/browser/resources/',
        'src/third_party/WebKit/',
        'src/media/',
        'src/sdch/',
        'src/testing/',
        'src/third_party/',
        'src/tools/',
        'src/'
    ]

    self.assertEqual(
        ProjectClassifier().project_classifier_config['host_directories'],
        expected_sorted_host_list)
