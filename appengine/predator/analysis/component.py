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
    return super(cls, Component).__new__(
        cls, component_name, tuple(dirs),
        re.compile(function) if function else None, team)

  def MatchesFilePath(self, file_path):
    """Determines whether this file_path belongs to this component or not."""
    file_path = file_path.lower()
    for directory in self.dirs:
      if file_path.startswith(directory.lower() + '/'):
        return True, directory

    return False, None
