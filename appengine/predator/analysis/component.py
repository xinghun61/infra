# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
import os
import re

from libs.gitiles.diff import ChangeType


# TODO(http://crbug.com/659346): write the coverage tests.
class Component(namedtuple('Component',
    ['component_name', 'dirs', 'function', 'team'])): # pragma: no cover
  """A representation of a "component" in Chromium.

  For example: 'Blink>DOM' or 'Blink>HTML'. Notably, a component knows
  how to identify itself. Hence, given a stack frame or change list
  or whatever, we ask the Component whether it matches that frame,
  CL, etc.
  """
  __slots__ = ()

  def __new__(cls, component_name, dirs, function=None, team=None):
    directories = []
    for directory in dirs:
      directories.append(directory if directory.endswith('/') else
                         directory + '/')

    return super(cls, Component).__new__(
        cls, component_name, tuple(directories),
        re.compile(function) if function else None, team)

  def MatchesStackFrame(self, frame):
    """Returns true if this component matches the frame."""
    if self.function and not self.function.match(frame.function):
      return False
    if frame.dep_path is None or frame.file_path is None:
      return False

    file_path = os.path.join(frame.dep_path, frame.file_path)
    return any(file_path.startswith(directory) for directory in self.dirs)

  def MatchesTouchedFile(self, dep_path, file_path):
    """Returns true if the touched file belongs to this component."""
    file_path = os.path.join(dep_path, file_path)
    return any(file_path.startswith(directory) for directory in self.dirs)
