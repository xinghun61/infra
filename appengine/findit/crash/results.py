# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

_INFINITY = 1000


class Result(object):
  """Represents findit culprit result."""

  def __init__(self, changelog, dep_path,
               confidence=None, reason=None):
    self.changelog = changelog
    self.dep_path = dep_path
    self.confidence = confidence
    self.reason = reason

    self.file_to_stack_infos = {}

  def ToDict(self):
    return {
        'url': self.changelog.commit_url,
        'review_url': self.changelog.code_review_url,
        'revision': self.changelog.revision,
        'project_path': self.dep_path,
        'author': self.changelog.author_email,
        'time': str(self.changelog.author_time),
        'reason': self.reason,
        'confidence': self.confidence,
    }

  def ToString(self):
    if not self.file_to_stack_infos:
      return ''

    lines = []
    for file_path, stack_infos in self.file_to_stack_infos.iteritems():
      line_parts = []
      for frame, _ in stack_infos:
        line_parts.append('%s (#%d)' % (frame.function, frame.index))

      lines.append('Changed file %s crashed in %s' % (
          file_path, ', '.join(line_parts)))

    return '\n'.join(lines)

  def __str__(self):
    return self.ToString()


class MatchResult(Result):
  """Represents findit culprit result got from match algorithm."""

  def __init__(self, changelog, dep_path,
               confidence=None, reason=None):
    super(MatchResult, self).__init__(
        changelog, dep_path, confidence, reason)

    self.min_distance = _INFINITY

  def Update(self, file_path, stack_infos, blame):
    """Updates a match result with file path and its stack_infos and blame.

    When a file_path is found both shown in stacktrace and touched by
    the revision of this result, update result with the information of
    this file.

    Inserts the file path and its stack infos, and updates the min distance
    if less distance is found between touched lines of this result and
    crashed lines in the file path.

    Args:
      file_path (str): File path of the crashed file.
      stack_infos (list): List of (StackFrame, callstack priority) tuples,
        represents frames of this file and the callstack priorities of those
        frames.
      blame (Blame): Blame oject of this file.
    """
    self.file_to_stack_infos[file_path] = stack_infos

    if not blame:
      return

    for region in blame:
      if region.revision != self.changelog.revision:
        continue

      region_lines = range(region.start, region.start + region.count)

      for frame, _ in stack_infos:
        self.min_distance = min(self.min_distance, self._DistanceOfTwoRegions(
            frame.crashed_line_numbers, region_lines))

  def _DistanceOfTwoRegions(self, region1, region2):
    if set(region1).intersection(set(region2)):
      return 0

    if region1[-1] < region2[0]:
      return region2[0] - region1[-1]

    return region1[0] - region2[-1]


class MatchResults(dict):
  """A dict indexing MatchResult with its revision."""

  def __init__(self, ignore_cls=None):
    super(MatchResults, self).__init__()
    self.ignore_cls = ignore_cls

  def GenerateMatchResults(self, file_path, dep_path,
                           stack_infos, changelogs, blame):
    """Generates match results.

    Match results are generated based on newly found file path, its stack_infos,
    and all the changelogs that touched this file in the dep in regression
    ranges, those reverted changelogs should be ignored.

    Args:
      file_path (str): File path of the crashed file.
      dep_path (str): Path of the dependency of the file.
      stack_infos (list): List of (StackFrame, callstack priority) tuples,
        represents frames of this file and the callstack priorities of those
        frames.
      changelogs (list): List of Changelog objects in the dep in regression
        range which touched the file.
      blame (Blame): Blame of the file.
    """
    for changelog in changelogs:
      if self.ignore_cls and changelog.revision in self.ignore_cls:
        continue

      if changelog.revision not in self:
        self[changelog.revision] = MatchResult(changelog, dep_path)

      match_result = self[changelog.revision]

      match_result.Update(file_path, stack_infos, blame)
