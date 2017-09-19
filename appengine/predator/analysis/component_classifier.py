# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
from collections import defaultdict
import functools
import logging
import os
import re

from analysis.component import Component
from analysis.occurrence import RankByOccurrence
from libs.gitiles.diff import ChangeType


def MergeComponents(components):
  """Given a list of components, merges components with the same hierarchy.

  For components with same hierarchy, return the most fine-grained component.
  For example, if components are ['Blink', 'Blink>Editing'], we should only
  return ['Blink>Editing'].
  """
  if not components or len(components) == 1:
    return components

  components.sort()
  merged_components = []
  index = 1
  while index < len(components):
    if not components[index].startswith(components[index - 1] + '>'):
      merged_components.append(components[index - 1])

    index += 1

  merged_components.append(components[-1])
  return merged_components


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

  def ClassifyFilePath(self, file_path):
    """Determines which component is responsible for this file_path."""
    component_to_dir_level = {}
    for component in self.components:
      match, directory = component.MatchesFilePath(file_path)
      if match:
        component_to_dir_level[component.component_name] = directory.count('/')

    # Returns components with longest directory path.
    return (max(component_to_dir_level,
                key=lambda component: component_to_dir_level[component])
            if component_to_dir_level else None)

  def ClassifyStackFrame(self, frame):
    """Determines which component is responsible for this frame."""
    if frame.dep_path is None or frame.file_path is None:
      return None

    file_path = os.path.join(frame.dep_path, frame.file_path)
    return self.ClassifyFilePath(file_path)

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
    return MergeComponents(RankByOccurrence(components, top_n_components))

  def ClassifyTouchedFile(self, dep_path, touched_file):
    """Determine which component is responsible for a touched file."""
    file_path = os.path.join(dep_path, touched_file.changed_path)
    return self.ClassifyFilePath(file_path)

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

    return MergeComponents(RankByOccurrence(
        components, top_n_components,
        rank_function=lambda x: -len(x)))

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
