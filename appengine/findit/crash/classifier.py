# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
from collections import OrderedDict

from common import constants
from crash.type_enums import CallStackLanguageType
from model.crash.crash_config import CrashConfig


class ClassOccurrenceInfo(object):
  """Represents information of a class in results or crash_stack.

  Class information includes the name of the class, a list of indice (index in
  results list or in the crash_stack) of occurrences.
  Class can be project name, like 'chromium', 'chromium-skia', or component name
  like 'Blink>API', 'Blink>DOM'.
  """

  def __init__(self, name, occurrences):
    self.name = name
    self.occurrences = occurrences


def DefaultRankFunction(class_info):
  """Default rank function to rank classes.

  Note: The default behavior works for component classifier and for
  project classifier, it works for cpp callstack class ranking.
  """
  # If the top 2 frames are in the same class, give this class highest
  # priority.
  if 0 in class_info.occurrences and 1 in class_info.occurrences:
    return -float('inf'), class_info.occurrences[0]

  return -len(class_info.occurrences), class_info.occurrences[0]


# TODO(http://crbug.com/644476): this class needs a better name.
class Classifier(object):
  """Classifies results or crash stack into a class or a list of classes."""

  def GetClassFromStackFrame(self, frame):  # pragma: no cover.
    raise NotImplementedError()

  def GetClassFromResult(self, result):  # pragma: no cover.
    raise NotImplementedError()

  def _Classify(self, results, crash_stack, top_n, max_classes,
                rank_function=DefaultRankFunction):
    """Classifies a crash to a list of classes, ranked by rank_function.

    Extracts a list of classes from results or crash_stack, rank the classes and
    returns max_classes number of classes on the top.

    Args:
      results (list of Result): Culprit results.
      crash_stack (CallStack): The callstack that caused the crash.
      top_n (int): Number of top frames to be considered when classifying.
      max_classes (int): Maximal number of classes to return.
      rank_function (function): Used to rank classes based on
        ClassOccurrenceInfos.

    Returns:
      A list of classes of this crash.
    """
    # Extracts the class list from culprit results if possible since it's more
    # reliable.
    if results:
      class_list = map(self.GetClassFromResult, results[:top_n])
    else:
      class_list = map(self.GetClassFromStackFrame, crash_stack[:top_n])

    def _GetClassOccurrenceInfos():
      """Gets ClassOccurrenceInfo list from class_list."""
      if not class_list:
        return class_list

      infos = {}

      # Get occurences information of each class.
      for index, class_name in enumerate(class_list):
        if class_name not in infos:
          infos[class_name] = ClassOccurrenceInfo(class_name, [index])
        else:
          infos[class_name].occurrences.append(index)

      return infos.values()

    class_infos = _GetClassOccurrenceInfos()
    class_infos = sorted(class_infos, key=rank_function)

    # Filter all empty class.
    classes = [info.name for info in class_infos if info.name]

    return classes[:max_classes]

  def Classify(self, results, crash_stack):  # pragma: no cover.
    raise NotImplementedError()
