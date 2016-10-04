# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import constants
from common.pipeline_wrapper import pipeline_handlers
from crash.classifier import Occurrence
from crash.classifier import Classifier
from crash.classifier import DefaultRankFunction
from crash.stacktrace import StackFrame
from crash.stacktrace import CallStack
from crash.results import Result
from crash.test.crash_testcase import CrashTestCase


class DummyClassifier(Classifier):

  def GetClassFromStackFrame(self, frame):
    if frame.dep_path == 'src/':
      return 'class_1'

    return 'class_2'

  def GetClassFromResult(self, result):  # pragma: no cover.
    return 'class_3'

  def Classify(self, results, crash_stack):
    class_list = self._Classify(results, crash_stack, 4, 1)
    if class_list:
      return class_list[0]

    return ''


class ClassifierTest(CrashTestCase):

  def testDefaultRankFunction(self):
    self.assertEqual(DefaultRankFunction(Occurrence('c1', [0])),
        (-1, 0))
    self.assertEqual(DefaultRankFunction(Occurrence('c1', [0, 1])),
        (-float('inf'), 0))

  def testClassifyCrashStack(self):
    dummy_classifier = DummyClassifier()

    crash_stack = CallStack(0)
    self.assertEqual(dummy_classifier.Classify([], crash_stack), '')

    crash_stack.extend(
        [StackFrame(0, 'src/', 'a::c(p* &d)', 'f0.cc', 'src/f0.cc', [177]),
         StackFrame(1, 'src/', 'a::d(a* c)', 'f1.cc', 'src/f1.cc', [227]),
         StackFrame(2, 'src/dummy', 'a::e(int)', 'f2.cc', 'src/f2.cc', [87])])

    self.assertEqual(dummy_classifier.Classify([], crash_stack), 'class_1')

    crash_stack = CallStack(0)
    crash_stack.extend(
        [StackFrame(0, 'src/', 'a::c(p* &d)', 'f0.cc', 'src/f0.cc', [177]),
         StackFrame(1, 'src/dummy', 'a::d(a* c)', 'f1.cc', 'src/f1.cc', [227]),
         StackFrame(2, 'src/dummy', 'a::e(int)', 'f2.cc', 'src/f2.cc', [87])])

    self.assertEqual(dummy_classifier.Classify([], crash_stack), 'class_2')

  def testClassifyResults(self):
    dummy_classifier = DummyClassifier()

    result = Result(self.GetDummyChangeLog(), 'src/')
    result.file_to_stack_infos = {
        'f0.cc': [(StackFrame(
            0, 'src/', 'a::c(p* &d)', 'f0.cc', 'src/f0.cc', [177]), 0)]
    }

    self.assertEqual(dummy_classifier.Classify([result], CallStack(0)),
                     'class_3')


