# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple


# TODO(wrengr): we should change things to use integers with None as
# \"infinity\", rather than using floats.
# TODO(http://crbug.com/644476): this class needs a better name.
class AnalysisInfo(namedtuple('AnalysisInfo',
    ['min_distance', 'min_distance_frame'])):
  __slots__ = ()

  def __str__(self): # pragma: no cover
    return ('AnalysisInfo(min_distance = %d, min_distance_frame = %s)'
        % (self.min_distance, self.min_distance_frame))


# TODO(wrengr): it's not clear why the ``priority`` is stored at all,
# given that every use in this file discards it. ``Result.file_to_stack_infos``
# should just store pointers directly to the frames themselves rather
# than needing this intermediate object.
# TODO(http://crbug.com/644476): this class needs a better name.
class StackInfo(namedtuple('StackInfo', ['frame', 'priority'])):
  """Pair of a frame and the ``priority`` of the ``CallStack`` it came from."""
  __slots__ = ()

  def __str__(self): # pragma: no cover
    return 'StackInfo(frame = %s, priority = %f)' % (self.frame, self.priority)


# TODO(wrengr): break this into separate unanalyzed suspect, and analyzed
# suspect; so we can distinguish the input to ``ChangelistClassifier``
# from the output of it (which will amend each suspect with extra metadata
# like the confidence and reasons).
class Suspect(object):
  """A suspected changelog to be classified as a possible ``Culprit``.

  That is, for each ``CrashReport`` the ``Predator.FindCulprit`` method
  receives, it will generate a bunch of these suspects and then inspect
  them to determine the ``Culprit`` it returns.
  """

  def __init__(self, changelog, dep_path,
               confidence=None, reasons=None, changed_files=None):
    assert isinstance(confidence, (int, float, type(None))), TypeError(
        'In the ``confidence`` argument to the Result constructor, '
        'expected a number or None, but got a %s object instead.'
        % confidence.__class__.__name__)
    self.changelog = changelog
    self.dep_path = dep_path
    self.confidence = None if confidence is None else float(confidence)
    self.reasons = reasons
    self.changed_files = changed_files

    # TODO(wrengr): (a) make these two fields private/readonly
    # TODO(wrengr): (b) zip them together.
    # TODO(wrengr): (c) move them to the relevant features instead.
    self.file_to_stack_infos = {}
    self.file_to_analysis_info = {}

  def ToDict(self):
    return {
        'url': self.changelog.commit_url,
        'review_url': self.changelog.code_review_url,
        'revision': self.changelog.revision,
        'project_path': self.dep_path,
        'author': self.changelog.author_email,
        'time': str(self.changelog.author_time),
        'reasons': self.reasons,
        'changed_files': self.changed_files,
        'confidence': self.confidence,
    }

  # TODO(katesonia): This is unusable for logging because in all the
  # cases that need logging it returns the empty string! We should print
  # this out in a more useful way (e.g., how CrashConfig is printed)
  # so that callers don't have to use ``str(result.ToDict())`` instead. If
  # we want a method that does what this one does, we should give it a
  # different name that indicates what it's actually printing out.
  def ToString(self):
    if not self.file_to_stack_infos:
      return ''

    lines = []
    for file_path, stack_infos in self.file_to_stack_infos.iteritems():
      line_parts = []
      for frame, _ in stack_infos:
        line_parts.append('frame #%d' % frame.index)

      lines.append('Changed file %s crashed in %s' % (
          file_path, ', '.join(line_parts)))

    return '\n'.join(lines)

  def __str__(self):
    return self.ToString()


def _UpdateSuspect(suspect, file_path, stack_infos, blame):
  """Updates a ``Suspect`` with file path and its stack_infos and blame.

  When a file_path is found both shown in stacktrace and touched by
  the revision of this result, update result with the information of
  this file.

  Inserts the file path and its stack infos, and updates the min distance
  if less distance is found between touched lines of this result and
  crashed lines in the file path.

  Args:
    suspect (Suspect): the suspect to be updated.
    file_path (str): File path of the crashed file.
    stack_infos (list of StackInfo): List of the frames of this file
      together with their callstack priorities.
    blame (Blame): Blame oject of this file.
  """
  suspect.file_to_stack_infos[file_path] = stack_infos

  if not blame:
    return

  min_distance = float('inf')
  min_distance_frame = stack_infos[0][0]
  for region in blame:
    if region.revision != suspect.changelog.revision:
      continue

    region_start = region.start
    region_end = region_start + region.count - 1
    for frame, _ in stack_infos:
      frame_start = frame.crashed_line_numbers[0]
      frame_end = frame.crashed_line_numbers[-1]
      distance = _DistanceBetweenLineRanges((frame_start, frame_end),
                                            (region_start, region_end))
      if distance < min_distance:
        min_distance = distance
        min_distance_frame = frame

  suspect.file_to_analysis_info[file_path] = AnalysisInfo(
      min_distance = min_distance,
      min_distance_frame = min_distance_frame,
  )


def _DistanceBetweenLineRanges((start1, end1), (start2, end2)):
  """Given two ranges, compute the (unsigned) distance between them.

  Args:
    start1: the start of the first range
    end1: the end of the first range. Must be greater than start1.
    start2: the start of the second range
    end2: the end of the second range. Must be greater than start2.

  Returns:
    If the end of the earlier range comes before the start of the later
    range, then the difference between those points. Otherwise, returns
    zero (because the ranges overlap)."""
  assert end1 >= start1, ValueError(
      'the first range is empty: %d < %d' % (end1, start1))
  assert end2 >= start2, ValueError(
      'the second range is empty: %d < %d' % (end2, start2))
  # There are six possible cases, but in all the cases where the two
  # ranges overlap, the latter two differences will be negative.
  return max(0, start2 - end1, start1 - end2)


class SuspectMap(dict):
  """A map from revisions to the ``Suspect`` object for that revision."""

  def __init__(self, ignore_cls=None):
    super(SuspectMap, self).__init__()
    self._ignore_cls = ignore_cls

  def GenerateSuspects(self, file_path, dep_path, stack_infos, changelogs,
      blame):
    """Compute suspects from a list of CLs, and store them in this map.

    Suspects are generated based on newly found file path, its stack_infos,
    and all the changelogs that touched this file in the dep in regression
    ranges, those reverted changelogs should be ignored.

    Args:
      file_path (str): File path of the crashed file.
      dep_path (str): Path of the dependency of the file.
      stack_infos (list): List of stack_info dicts, represents frames of this
        file and the callstack priorities of those frames.
      changelogs (list): List of Changelog objects in the dep in regression
        range which touched the file.
      blame (Blame): Blame of the file.
    """
    for changelog in changelogs:
      if self._ignore_cls and changelog.revision in self._ignore_cls:
        continue

      if changelog.revision not in self:
        self[changelog.revision] = Suspect(changelog, dep_path)

      _UpdateSuspect(self[changelog.revision], file_path, stack_infos, blame)
