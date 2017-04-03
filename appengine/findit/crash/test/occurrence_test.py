# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import constants
from crash.occurrence import Occurrence
from crash.occurrence import DefaultOccurrenceRanking
from crash.occurrence import RankByOccurrence
from crash.stacktrace import StackFrame
from crash.stacktrace import CallStack
from crash.suspect import Suspect
from crash.test.predator_testcase import PredatorTestCase
from gae_libs.pipeline_wrapper import pipeline_handlers


class DummyClassifier(object):

  def GetClassFromStackFrame(self, frame):
    if frame.dep_path == 'src/':
      return 'class_1'

    if frame.dep_path == 'dummy/':
      return None

    return 'class_2'

  def GetClassFromSuspect(self, _result):  # pragma: no cover.
    return 'class_3'

  def Classify(self, results, crash_stack):
    top_n_frames = 4
    if results:
      classes = map(self.GetClassFromSuspect, results[:top_n_frames])
    else:
      classes = map(self.GetClassFromStackFrame,
          crash_stack.frames[:top_n_frames])

    class_list = RankByOccurrence(classes, 1)
    if class_list:
      return class_list[0]

    return ''


class ClassifierTest(PredatorTestCase):

  def testDefaultOccurrenceRanking(self):
    self.assertEqual(DefaultOccurrenceRanking(Occurrence('c1', [0])),
        (-1, 0))
    self.assertEqual(DefaultOccurrenceRanking(Occurrence('c1', [0, 1])),
        (-float('inf'), 0))

  def testClassifyCrashStack(self):
    dummy_classifier = DummyClassifier()

    crash_stack = CallStack(0)
    self.assertEqual(dummy_classifier.Classify([], crash_stack), '')

    crash_stack = CallStack(0, frame_list=[
        StackFrame(0, 'src/', 'a::c(p* &d)', 'f0.cc', 'src/f0.cc', [177]),
        StackFrame(1, 'src/', 'a::d(a* c)', 'f1.cc', 'src/f1.cc', [227]),
        StackFrame(2, 'src/dummy', 'a::e(int)', 'f2.cc', 'src/f2.cc', [87]),
        StackFrame(3, 'dummy/', 'a::g(int)', 'f3.cc', 'src/f3.cc', [87])])

    self.assertEqual(dummy_classifier.Classify([], crash_stack), 'class_1')

    crash_stack = CallStack(0, frame_list=[
        StackFrame(0, 'src/', 'a::c(p* &d)', 'f0.cc', 'src/f0.cc', [177]),
        StackFrame(1, 'src/dummy', 'a::d(a* c)', 'f1.cc', 'src/f1.cc', [227]),
        StackFrame(2, 'src/dummy', 'a::e(int)', 'f2.cc', 'src/f2.cc', [87])])

    self.assertEqual(dummy_classifier.Classify([], crash_stack), 'class_2')

  def testClassifySuspects(self):
    dummy_classifier = DummyClassifier()

    suspect = Suspect(self.GetDummyChangeLog(), 'src/')
    suspect.file_to_stack_infos = {
        'f0.cc': [(StackFrame(
            0, 'src/', 'a::c(p* &d)', 'f0.cc', 'src/f0.cc', [177]), 0)]
    }

    self.assertEqual(dummy_classifier.Classify([suspect], CallStack(0)),
                     'class_3')

