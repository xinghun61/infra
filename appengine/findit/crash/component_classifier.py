# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from crash.classifier import Classifier
from model.crash.crash_config import CrashConfig


class ComponentClassifier(Classifier):
  """Determines the component of a crash.

  For example: ['Blink>DOM', 'Blink>HTML'].
  """

  def __init__(self):
    super(ComponentClassifier, self).__init__()
    self.component_classifier_config = (
        CrashConfig.Get().compiled_component_classifier)

  def GetClassFromStackFrame(self, frame):
    """Gets the component from file path and function of a frame."""
    for path_regex, function_regex, component in (
        self.component_classifier_config['path_function_component']):
      path_match = path_regex.match(frame.dep_path + frame.file_path)
      if not path_match:
        continue

      if not function_regex:
        return component

      function_match = function_regex.match(frame.function)
      if function_match:
        return component

    return ''

  def GetClassFromResult(self, result):
    """Gets the component from a result.

    Note that Findit assumes files that the culprit result touched come from
    the same component.
    """
    if result.file_to_stack_infos:
      # A file in culprit result should always have its stack_info, namely a
      # list of (frame, callstack_priority) pairs.
      frame, _ = result.file_to_stack_infos.values()[0][0]
      return self.GetClassFromStackFrame(frame)

    return ''

  def Classify(self, results, crash_stack):
    """Classifies project of a crash.

    Args:
      results (list of Result): Culprit results.
      crash_stack (CallStack): The callstack that caused the crash.

    Returns:
      List of top 2 components.
    """
    if not self.component_classifier_config:
      logging.warning('Empty configuration for component classifier.')
      return []

    return self._Classify(results, crash_stack,
                          self.component_classifier_config['top_n'], 2)
