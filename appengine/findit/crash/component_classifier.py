# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
import logging
import re

from crash.classifier import Classifier


# TODO(wrengr): write coverage tests the old version was lacking.
class Component(namedtuple('Component',
    ['component_name', 'path_regex', 'function_regex'])): # pragma: no cover
  """A representation of a "component" in Chromium.

  For example: 'Blink>DOM' or 'Blink>HTML'. Notably, a component knows
  how to identify itself. Hence, given a stack frame or change list
  or whatever, we ask the Component whether it matches that frame,
  CL, etc."""
  __slots__ = ()

  def __new__(cls, component_name, path_regex, function_regex=None):
    return super(cls, Component).__new__(cls,
      component_name,
      re.compile(path_regex),
      re.compile(function_regex) if function_regex else None)

  def MatchesStackFrame(self, frame):
    """Return true if this component matches the frame."""
    if not self.path_regex.match(frame.dep_path + frame.file_path):
      return False

    # We interpret function_regex=None to mean the regex that matches
    # everything.
    if not self.function_regex:
      return True
    return self.function_regex.match(frame.function)


class ComponentClassifier(Classifier):
  """Determines the component of a crash.

  For example: ['Blink>DOM', 'Blink>HTML'].
  """

  def __init__(self, components, top_n):
    """Build a classifier for components.

    Args:
      components (list of crash.component.Component): the components to
        check for.
      top_n (int): how many frames of the callstack to look at"""
    super(ComponentClassifier, self).__init__()
    if not components:
      logging.warning('Empty configuration for component classifier.')
      components = [] # Ensure self.components is not None
    self.components = components
    self.top_n = top_n

  def GetClassFromStackFrame(self, frame):
    """Determine which component is responsible for this frame."""
    for component in self.components:
      if component.MatchesStackFrame(frame):
        return component.component_name

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
    return self._Classify(results, crash_stack, self.top_n, 2)
