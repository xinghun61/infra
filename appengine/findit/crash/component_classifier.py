# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
from collections import defaultdict
import logging
import re

from crash.component import Component
from crash.occurrence import RankByOccurrence
from libs.gitiles.diff import ChangeType


class ComponentClassifier(object):
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

  # TODO(wrengr): refactor this into a method on Result which returns
  # the cannonical frame (and documents why it's the one we return).
  def GetClassFromResult(self, result):
    """Determine which component is responsible for this result.

    Note that Findit assumes files that the culprit result touched come from
    the same component.
    """
    if result.file_to_stack_infos:
      # file_to_stack_infos is a dict mapping file_path to stack_infos,
      # where stack_infos is a list of (frame, callstack_priority)
      # pairs. So ``.values()`` returns a list of the stack_infos in an
      # arbitrary order; the first ``[0]`` grabs the "first" stack_infos;
      # the second ``[0]`` grabs the first pair from the list; and
      # the third ``[0]`` grabs the ``frame`` from the pair.
      # TODO(wrengr): why is that the right frame to look at?
      frame = result.file_to_stack_infos.values()[0][0][0]
      return self.GetClassFromStackFrame(frame)

    return ''

  # TODO(http://crbug.com/657177): return the Component objects
  # themselves, rather than strings naming them.
  def Classify(self, results, crash_stack):
    """Classifies component of a crash.

    Args:
      results (list of Result): Culprit results.
      crash_stack (CallStack): The callstack that caused the crash.

    Returns:
      List of top 2 components.
    """
    # If ``results`` are available, we use the components from there since
    # they're more reliable than the ones from the ``crash_stack``.
    if results:
      classes = map(self.GetClassFromResult, results[:self.top_n])
    else:
      classes = map(self.GetClassFromStackFrame, crash_stack[:self.top_n])

    return RankByOccurrence(classes, 2)

  # TODO(ymzhang): use component of new path as default. RENAME might
  # need to return two (old path new path may have different components)
  def GetClassFromFileChangeInfo(self, file_change_info):
    """Determine which component is responsible for a touched file."""
    if not file_change_info:
      return None

    for component in self.components:
      if (file_change_info.change_type == ChangeType.DELETE):
        if component.MatchesFile(file_change_info.old_path):
          return component.component_name
      else:
        if component.MatchesFile(file_change_info.new_path):
          return component.component_name

    return ''

  def ClassifyChangeLog(self, change_log, top_n=2):
    """ Classifies components of a change log.

     Args:
       change_log: a change log
       top_n: number of components assigned to this change log, default is 2

     Returns:
       List of components
     """
    if not change_log:
      return None

    classes = map(self.GetClassFromFileChangeInfo, change_log.touched_files)
    return RankByOccurrence(classes, top_n, rank_function=lambda x:-len(x))
