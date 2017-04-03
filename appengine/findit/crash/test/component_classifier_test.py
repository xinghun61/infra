# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from crash.stacktrace import StackFrame
from crash.stacktrace import CallStack
from crash.component_classifier import Component
from crash.component_classifier import ComponentClassifier
from crash.suspect import Suspect
from crash.test.predator_testcase import PredatorTestCase
from gae_libs.pipeline_wrapper import pipeline_handlers
from model.crash.crash_config import CrashConfig
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.diff import ChangeType


class ComponentClassifierTest(PredatorTestCase):
  """Tests ``ComponentClassifier`` class."""

  def setUp(self):
    super(ComponentClassifierTest, self).setUp()
    config = CrashConfig.Get().component_classifier
    components = [Component(component_name, path_regex, function_regex)
                  for path_regex, function_regex, component_name
                  in config['path_function_component']]
    # Only construct the classifier once, rather than making a new one every
    # time we call a method on it.
    self.classifier = ComponentClassifier(components, config['top_n'])

  def testClassifyCallStack(self):
    """Tests ``ClassifyCallStack`` method."""
    callstack = CallStack(
        0, [StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2])])
    self.assertEqual(self.classifier.ClassifyCallStack(callstack),
                     ['Comp1>Dummy'])

    callstack = CallStack(
        0, [StackFrame(0, 'dummy/', 'no_func', 'comp2.cc',
                       'dummy/comp2.cc', [32])])
    self.assertEqual(self.classifier.ClassifyCallStack(callstack), [])

    crash_stack = CallStack(0, frame_list=[
        StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]),
        StackFrame(1, 'src/', 'ff', 'comp1.cc', 'src/comp1.cc', [21]),
        StackFrame(2, 'src/', 'func2', 'comp2.cc', 'src/comp2.cc', [8])])

    self.assertEqual(self.classifier.ClassifyCallStack(crash_stack),
                     ['Comp1>Dummy', 'Comp2>Dummy'])

  def testClassifySuspect(self):
    """Tests ``ClassifySuspect`` method."""
    suspect = Suspect(self.GetDummyChangeLog(), 'src/')
    suspect.changelog = suspect.changelog._replace(
        touched_files = [FileChangeInfo(ChangeType.MODIFY,
                                        'comp1.cc', 'comp1.cc')])
    self.assertEqual(self.classifier.ClassifySuspect(suspect), ['Comp1>Dummy'])

  def testClassifyEmptySuspect(self):
    """Tests ``ClassifySuspect`` returns None for empty suspect."""
    self.assertIsNone(self.classifier.ClassifySuspect(None))

  def testClassifySuspectNoMatch(self):
    """Tests ``ClassifySuspect`` returns None if there is no file match."""
    suspect = Suspect(self.GetDummyChangeLog(), 'dummy')
    suspect.changelog = suspect.changelog._replace(
        touched_files = [FileChangeInfo(ChangeType.MODIFY,
                                        'comp1.cc', 'comp1.cc')])
    self.assertEqual(self.classifier.ClassifySuspect(suspect), [])

  def testClassifySuspects(self):
    """Tests ``ClassifySuspects`` classify a list of ``Suspect``s."""
    suspect1 = Suspect(self.GetDummyChangeLog(), 'src/')
    suspect1.changelog = suspect1.changelog._replace(
        touched_files = [FileChangeInfo(ChangeType.MODIFY,
                                        'comp1.cc', 'comp1.cc')])
    suspect2 = Suspect(self.GetDummyChangeLog(), 'src/')
    suspect2.changelog = suspect2.changelog._replace(
        touched_files = [FileChangeInfo(ChangeType.MODIFY,
                                        'comp2.cc', 'comp2.cc')])

    self.assertEqual(self.classifier.ClassifySuspects([suspect1, suspect2]),
                     ['Comp1>Dummy', 'Comp2>Dummy'])
