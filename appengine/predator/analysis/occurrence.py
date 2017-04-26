# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class Occurrence(list):
  """A list of indices where something occurs in a list.

  The list of indices can be accessed directly, since this class is a
  subclass of ``list``. In addition to this list, we also have a ``name`
  property which specifies what thing is occurring in those positions. For
  our uses here, the name is a string denoting either a project name
  (e.g., 'chromium' or 'chromium-skia') or a component name (e.g.,
  'Blink>API' or 'Blink>DOM').
  """
  def __init__(self, name, indices=None):
    super(Occurrence, self).__init__(indices or [])
    self._name = name

  # TODO(http://crbug.com/644476): even though "name" is fine for our
  # use case (strings identifying Projects & Components), we should
  # probably use a more general name for this.
  @property
  def name(self):
    """The \"name\" this object is a list of occurrence indices for."""
    return self._name


def GetOccurrences(names):
  """Returns a concordance of elements in a list.

  Args:
    names (list): a list of "names". Typically names are strings, but
      they're actually allowed to be anything which can serve as a key
      in a dict.

  Returns:
    A dict mapping each "name" in ``names`` to an Occurrence object,
    each of which contains a list of the indices where that name occurs
    in ``names``.
  """
  occurrences = {}
  for index, name in enumerate(names or []):
    if not name:
      continue

    if name not in occurrences:
      occurrences[name] = Occurrence(name, [index])
    else:
      occurrences[name].append(index)

  return occurrences


def DefaultOccurrenceRanking(occurrence):
  """Default function for ranking an occurrence.

  Note: The default behavior works for component classifier and for
  project classifier, it works for cpp callstack class ranking.

  Args:
    occurrence (Occurrence): a collection of indices where some "name"
      occured in a sequence.

  Returns:
    A pair of the weight/priority for this ``occurrence``, and the index
    of the first time its name appeared in the sequence the ``occurrence``
    came from.
  """
  # If the first two elements in the sequence are in this class, then
  # give it highest priority.
  if 0 in occurrence and 1 in occurrence:
    return -float('inf'), occurrence[0]

  return -len(occurrence), occurrence[0]


# TODO(wrengr): it'd be nice to have the ranking function decide how
# much of the input sequence to look at, rather than the caller deciding
# once and for all. Of course, doing that would mean having the
# ``Occurrence`` class lazily traverse the sequence, with some sort of
# productivity guarantee.
def RankByOccurrence(names, top_n, rank_function=None):
  """Rank the things occurring in a sequence according to some function.

  Given any sequence of "names", construct a concordance and return
  the few highest-ranking names according to a function for ranking
  ``Occurrence``s. N.B., this function is generic in the length of the
  input sequence, so it's up to callers to truncate the sequence if
  they so desire.

  Args:
    names (list): a list of "names". Typically names are strings, but
      they're actually allowed to be anything which can serve as a key
      in a dict.
    top_n (int): how many results to return.
    rank_function (callable): what rank value to give an occurrence. If
      you don't supply this argument, or if you provide a falsy value,
      then we will fall back to using the ``DefaultOccurrenceRanking``.

  Returns:
    A length-``top_n`` list of "names" ordered by the ``rank_function``.
  """
  if not rank_function:  # pragma: no cover.
    rank_function = DefaultOccurrenceRanking

  # TODO(wrengr): generalize the filter function into another parameter.
  occurrences = sorted(GetOccurrences(names).values(), key=rank_function)

  return [occurrence.name for occurrence in occurrences[:top_n]]
