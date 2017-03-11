# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
from collections import defaultdict
import functools
import logging
import re

from crash.component import Component
from crash.occurrence import RankByOccurrence
from libs.gitiles.diff import ChangeType


class ComponentClassifier(object):
  """Determines the component of a crash.

  For example: ['Blink>DOM', 'Blink>HTML'].
  """

  def __init__(self, components, top_n_frames):
    """Build a classifier for components.

    Args:
      components (list of crash.component.Component): the components to
        check for.
      top_n_frames (int): how many frames of the callstack to look at.
    """
    super(ComponentClassifier, self).__init__()
    self.components = components or []
    self.top_n_frames = top_n_frames

  def ClassifyStackFrame(self, frame):
    """Determine which component is responsible for this frame."""
    for component in self.components:
      if component.MatchesStackFrame(frame):
        return component.component_name

    return None

  # TODO(http://crbug.com/657177): return the Component objects
  # themselves, rather than strings naming them.
  def ClassifyCallStack(self, stack, top_n_components=2):
    """Classifies component of a crash.

    Args:
      stack (CallStack): The callstack that caused the crash.
      top_n_components (int): The number of top components for the stack,
        defaults to 2.

    Returns:
      List of top n components.
    """
    components = map(self.ClassifyStackFrame,
                     stack.frames[:self.top_n_frames])
    return RankByOccurrence(components, top_n_components)

  def ClassifyTouchedFile(self, dep_path, touched_file):
    """Determine which component is responsible for a touched file."""
    for component in self.components:
      if component.MatchesTouchedFile(dep_path,
                                      touched_file.changed_path):
        return component.component_name

    return None

  # TODO(http://crbug.com/657177): return the Component objects
  # themselves, rather than strings naming them.
  def ClassifySuspects(self, suspects, top_n_components=2):
    """Classifies component of a list of suspects.

    Args:
      suspects (list of Suspect): Culprit suspects.
      top_n_components (int): The number of top components for the stack,
        defaults to 2.

    Returns:
      List of top 2 components.
    """
    components = []
    for suspect in suspects:
      components.extend(self.ClassifySuspect(suspect))

    return RankByOccurrence(components, top_n_components,
                            rank_function=lambda x: -len(x))

  def ClassifySuspect(self, suspect, top_n_components=2):
    """ Classifies components of a suspect.

    Args:
      suspect (Suspect): a change log
      top_n_components (int): number of components assigned to this suspect,
        defaults to 2.

    Returns:
      List of components
    """
    if not suspect or not suspect.changelog:
      return None

    classify_touched_file_func = functools.partial(self.ClassifyTouchedFile,
                                                    suspect.dep_path)
    components = map(classify_touched_file_func,
                     suspect.changelog.touched_files)
    return RankByOccurrence(components, top_n_components,
                            rank_function=lambda x: -len(x))
