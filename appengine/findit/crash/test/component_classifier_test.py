# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.pipeline_wrapper import pipeline_handlers
from crash.callstack import StackFrame, CallStack
from crash.component_classifier import ComponentClassifier
from crash.results import Result
from crash.test.crash_testcase import CrashTestCase
from model.crash.crash_config import CrashConfig


class ComponentClassifierTest(CrashTestCase):

  def testGetClassFromStackFrame(self):
    frame = StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2])
    self.assertEqual(
        ComponentClassifier().GetClassFromStackFrame(frame),
        'Comp1>Dummy')

    frame = StackFrame(0, 'src/', 'func2', 'comp2.cc', 'src/comp2.cc', [32])
    self.assertEqual(
        ComponentClassifier().GetClassFromStackFrame(frame),
        'Comp2>Dummy')

    frame = StackFrame(0, 'src/', 'no_func', 'comp2.cc', 'src/comp2.cc', [32])
    self.assertEqual(
        ComponentClassifier().GetClassFromStackFrame(frame),
        '')

    frame = StackFrame(0, 'src/', 'func2', 'a.cc', 'src/a.cc', [6])
    self.assertEqual(
        ComponentClassifier().GetClassFromStackFrame(frame),
        '')

  def testGetClassFromResult(self):
    result = Result(self.GetDummyChangeLog(), 'src/')
    self.assertEqual(ComponentClassifier().GetClassFromResult(result),
                 '')

    result.file_to_stack_infos = {
        'comp1.cc': [
            (StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]), 0)
        ]
    }
    self.assertEqual(ComponentClassifier().GetClassFromResult(result),
                     'Comp1>Dummy')

  def testClassifyCrashStack(self):
    crash_stack = CallStack(0)
    crash_stack.extend([
        StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]),
        StackFrame(1, 'src/', 'ff', 'comp1.cc', 'src/comp1.cc', [21]),
        StackFrame(2, 'src/', 'func2', 'comp2.cc', 'src/comp2.cc', [8])
    ])

    self.assertEqual(ComponentClassifier().Classify([], crash_stack),
                     ['Comp1>Dummy', 'Comp2>Dummy'])

  def testClassifyResults(self):
    result = Result(self.GetDummyChangeLog(), 'src/')
    result.file_to_stack_infos = {
        'comp1.cc': [
            (StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]), 0)
        ]
    }

    self.assertEqual(ComponentClassifier().Classify([result], CallStack(0)),
                     ['Comp1>Dummy'])

  def testClassifierDoNotHaveConfig(self):
    crash_config = CrashConfig.Get()
    crash_config.component_classifier = {}

    crash_stack = CallStack(0)
    crash_stack.extend([
        StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]),
        StackFrame(1, 'src/', 'ff', 'comp1.cc', 'src/comp1.cc', [21]),
        StackFrame(2, 'src/', 'func2', 'comp2.cc', 'src/comp2.cc', [8])
    ])

    result = Result(self.GetDummyChangeLog(), 'src/')
    result.file_to_stack_infos = {
        'comp1.cc': [
            (StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]), 0)
        ]
    }

    self.assertEqual(ComponentClassifier().Classify([result], crash_stack),
                     [])
