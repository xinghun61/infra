# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
import os
import re

from libs.gitiles.diff import ChangeType


# TODO(http://crbug.com/659346): write the coverage tests.
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
    """Returns true if this component matches the frame."""
    if not self.path_regex.match(os.path.join(frame.dep_path, frame.file_path)):
      return False

    # We interpret function_regex=None to mean the regex that matches
    # everything.
    if not self.function_regex:
      return True
    return self.function_regex.match(frame.function)

  def MatchesTouchedFile(self, dep_path, file_path):
    """Returns true if the touched file belongs to this component."""
    return self.path_regex.match(os.path.join(dep_path, file_path))
