# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class Occurrence(list):
  """A list of indices where something occurs in a list.

  The list of indices can be accessed directly, since this class is a
  subclass of |list|. In addition to this list, we also have a |name|
  property which specifies what thing is occurring in those positions. For
  our uses here, the name is a string denoting either a project name
  (e.g., 'chromium' or 'chromium-skia') or a component name (e.g.,
  'Blink>API' or 'Blink>DOM').
  """
  def __init__(self, name, indices=None):
    super(Occurrence, self).__init__(indices or [])
    self.name = name


# TODO(wrengr): why not return the dict itself? Or if we're going to
# return a list, why not take in the ranking function so we can perform
# the sorting ourselves?
def GetOccurrences(names):
  """Return a concordance of elements in a list.

  Args:
    names (list): a list of "names". Typically names are strings, but
      they're actually allowed to be anything which can serve as a key
      in a dict.

  Returns:
    A list of Occurrence objects. For each name in |names| we produce
    an Occurrence object, which in turn contains a list of the indices
    where that name occurs in |names|.
  """
  occurrences = {}
  for index, name in enumerate(names or []):
    if name not in occurrences:
      occurrences[name] = Occurrence(name, [index])
    else:
      occurrences[name].append(index)

  return occurrences.values()


def DefaultRankFunction(class_occurrence):
  """Default function for ranking classes.

  Note: The default behavior works for component classifier and for
  project classifier, it works for cpp callstack class ranking.

  Returns:
    A pair of the weight/priority for this |class_occurrence|, and the
    index of the first occurrence of this class's name in the list the
    |class_occurrence| came from.
  """
  # If the top 2 frames are in this class, then give it highest priority.
  if 0 in class_occurrence and 1 in class_occurrence:
    return -float('inf'), class_occurrence[0]

  return -len(class_occurrence), class_occurrence[0]


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
      rank_function (function): Used to rank classes based on Occurrence.

    Returns:
      A list of classes for this crash, ordered by the |rank_function|.
    """
    # Extracts the class list from culprit results if possible since it's more
    # reliable.
    if results:
      classes = map(self.GetClassFromResult, results[:top_n])
    else:
      classes = map(self.GetClassFromStackFrame, crash_stack[:top_n])

    occurrences = sorted(GetOccurrences(classes), key=rank_function)

    # Filter out unnamed classes.
    classes = [occurrence.name for occurrence in occurrences if occurrence.name]

    return classes[:max_classes]

  def Classify(self, results, crash_stack):  # pragma: no cover.
    raise NotImplementedError()
