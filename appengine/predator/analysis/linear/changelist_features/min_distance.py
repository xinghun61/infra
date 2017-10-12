# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import math
import os

from analysis.crash_match import FrameInfo
from analysis.linear.feature import ChangedFile
from analysis.linear.feature import Feature
from analysis.linear.feature import FeatureValue
from analysis.linear.feature import LinearlyScaled
from libs.gitiles.diff import ChangeType

_MINIMUM_FEATURE_VALUE = 0
# N.B., this must not be infinity, else we'll start getting NaN values
# from LinearMinDistanceFeature (and SquaredMinDistanceFeature).
_DEFAULT_MAX_LINE_DISTANCE = 100


class Distance(object):
  """Represents the closest frame to a changelog which modified it.

  The "closest" means that the distance between crashed lines in the frame and
  touched lines in a changelog is minimum.

  Properties:
    distance (int or float('inf')): The distance between crashed lines and
      touched lines, if a changelog doesn't show in blame of the crashed file of
      the crashed version (either it didn't touch the crashed file or it got
      overwritten by other cls), the distance would be infinite.
    frame (StackFrame): The frame which has the minimum distance to touched
      lines.
  """

  def __init__(self, distance, frame):
    self.distance = distance
    self.frame = frame

  def Update(self, distance, frame):
    if distance < self.distance:
      self.distance = distance
      self.frame = frame

  # TODO(katesonia): we should change things to use integers with None as
  # \"infinity\", rather than using floats.
  def IsInfinity(self):
    return math.isinf(self.distance)

  def __str__(self):  # pragma: no cover
    return 'Min distance(distance = %f, frame = %s)' % (float(self.distance),
                                                        str(self.frame))

  def __eq__(self, other):
    return self.distance == other.distance and self.frame == other.frame


def DistanceBetweenLineRanges((start1, end1), (start2, end2)):
  """Given two ranges, compute the (unsigned) distance between them.

  Args:
    start1 (int): the first line included in the first range.
    end1 (int): the last line included in the first range. Must be
      greater than or equal to ``start1``.
    start2 (int): the first line included in the second range.
    end2 (int): the last line included in the second range. Must be
      greater than or equal to ``start2``.

  Returns:
    If the end of the earlier range comes before the start of the later
    range, then the difference between those points. Otherwise, returns
    zero (because the ranges overlap).
  """
  if end1 < start1:
    raise ValueError('the first range is empty: %d < %d' % (end1, start1))
  if end2 < start2:
    raise ValueError('the second range is empty: %d < %d' % (end2, start2))
  # There are six possible cases, but in all the cases where the two
  # ranges overlap, the latter two differences will be negative.
  return max(0, start2 - end1, start1 - end2)


class MinDistanceFeature(Feature):
  """Returns the minimum min_distance scaled between 0 and 1.

  If the distance is more than _DEFAULT_MAX_LINE_DISTANCE, the value is 0.
  If the distance is 0, the value is 1.0.
  For distance that is less than _DEFAULT_MAX_LINE_DISTANCE and more than 0,
  the value is linearly scaled between (0, 1).
  """
  def __init__(self, get_repository, maximum=_DEFAULT_MAX_LINE_DISTANCE):
    """
    Args:
      maximum (float): An upper bound on the min_distance to consider.
    """
    self._get_repository = get_repository
    self._maximum = maximum

  @property
  def name(self):
    return 'MinDistance'

  def DistanceBetweenTouchedFileAndFrameInfos(
      self, revision, touched_file, frame_infos, crash_dependency):
    """Gets ``Distance`` between touched and crashed lines in a file.

    Args:
      revision (str): The revision of the suspect.
      touched_file (FileChangeInfo): The file touched by the suspect.
      frame_infos (list of FrameInfos): List of information of frames in the
        stacktrace which contains ``touched_file``.
      crash_dependency (Dependency): The depedency of crashed revision. N.B. The
        crashed revision is the revision where crash happens, however the
        first parameter ``revision`` is the revision of the suspect cl, which
        must be before the crashed revision.

    Returns:
      ``Distance`` object of touched file and stacktrace.
    """
    # TODO(katesonia) ``GetBlame`` is called for the same file everytime
    # there is a suspect that touched it, which can be very expensive.
    # The blame information can either be cached through repository (cached
    # by memcache based on repo url, revision and file path), or this
    # function can have a static in-memory cache to cache blame for touched
    # files, however since blame information is big, it's not a good idea to
    # keep it in memory.
    if touched_file.change_type == ChangeType.DELETE:
      return None

    repository = self._get_repository(crash_dependency.repo_url)
    blame = repository.GetBlame(touched_file.new_path,
                                crash_dependency.revision)
    if not blame:
      logging.warning('Failed to get blame information for %s',
                      touched_file.new_path)
      return None

    # Distance of this file.
    distance = Distance(float('inf'), None)
    for region in blame:
      if region.revision != revision:
        continue

      region_start = region.start
      region_end = region_start + region.count - 1
      for frame_info in frame_infos:
        if not frame_info.frame.crashed_line_numbers:
          continue
        frame_start = frame_info.frame.crashed_line_numbers[0]
        frame_end = frame_info.frame.crashed_line_numbers[-1]
        line_distance = DistanceBetweenLineRanges((frame_start, frame_end),
                                                  (region_start, region_end))
        distance.Update(line_distance, frame_info.frame)

    return distance

  def __call__(self, report):
    """Returns the scaled min ``Distance.distance`` across all files.

    Args:
      report (CrashReport): the crash report being analyzed.

    Returns:
      A function from ``Suspect`` to the minimum distance between (the code
      for) a stack frame in that suspect and the CL in that suspect, as a
      log-domain ``float``.
    """
    def FeatureValueGivenReport(suspect, matches):
      """Function mapping suspect related data to MinDistance FeatureValue.

      Args:
        suspect (Suspect): The suspected changelog and some meta information
          about it.
        matches(dict): Dict mapping crashed group(CrashedFile, CrashedDirectory)
          to a list of ``Match``s representing all frames and all touched files
          matched in the same crashed group(same crashed file or crashed
          directory).

      Returns:
        The ``FeatureValue`` of this feature.
      """
      if not matches:
        FeatureValue(name=self.name,
                     value=0.0,
                     reason=None,
                     changed_files=None)

      distance = Distance(float('inf'), None)
      touched_file_to_distance = {}
      for match in matches.itervalues():
        if len(match.touched_files) != 1:
          logging.warning('There should be only one touched file per crashed '
                          'file group.')
          continue

        touched_file = match.touched_files[0]
        # Records the closest frame (the frame has minimum distance between
        # crashed lines and touched lines) for each touched file of the suspect.
        distance_per_file = self.DistanceBetweenTouchedFileAndFrameInfos(
            suspect.changelog.revision, touched_file,
            match.frame_infos, report.dependencies[suspect.dep_path])
        # Failed to get blame information of a file.
        if not distance_per_file:
          logging.warning('suspect\'s change cannot be blamed due to lack of'
                          'blame information for crashed file %s' %
                          touched_file.new_path)
          continue

        # It is possible that a changelog doesn't show in the blame of a file,
        # in this case, treat the changelog as if it didn't change the file.
        if distance_per_file.IsInfinity():
          continue

        touched_file_to_distance[touched_file] = distance_per_file
        distance.Update(distance_per_file.distance,
                        distance_per_file.frame)

      value = LinearlyScaled(float(distance.distance), float(self._maximum))
      if distance.frame is not None:
        reason = [
            'Suspected changelist touched lines near the crashing line in '
            '%s (%d lines away)' % (
                os.path.basename(distance.frame.file_path),
                int(distance.distance))]
      else:
        reason = None

      if value <= _MINIMUM_FEATURE_VALUE:
        changed_files = None
      else:
        changed_files = MinDistanceFeature.ChangedFiles(
              suspect, touched_file_to_distance,
              report.crashed_version)

      return FeatureValue(name=self.name,
                          value=value,
                          reason=reason,
                          changed_files=changed_files)

    return FeatureValueGivenReport

  @staticmethod
  def ChangedFiles(suspect, touched_file_to_distance, crashed_version):
    """Get all the changed files causing this feature to blame this result.

    Arg:
      suspect (Suspect): the suspect being blamed.
      touched_file_to_distance (dict): Dict mapping file name to
        ``Distance``s.
      crashed_version (str): Crashed version.

    Returns:
      List of ``ChangedFile`` objects sorted by frame index. For example:

        [ChangedFile(
            file = 'render_frame_impl.cc',
            blame_url = 'https://chr.com/../render_frame_impl.cc#1586',
            reasons = ['Minimum distance (LOC) 1, frame #5']
        )]
    """
    frame_index_to_changed_files = {}

    for touched_file, distance in (
        touched_file_to_distance.iteritems()):
      file_name = touched_file.new_path.split('/')[-1]
      if distance.frame is None: # pragma: no cover
        logging.warning('Missing the min_distance_frame for file %s' %
                        file_name)
        continue

      frame_index_to_changed_files[distance.frame.index] = ChangedFile(
              name=file_name,
              blame_url=distance.frame.BlameUrl(crashed_version),
              reasons=['Distance between touched lines and stacktrace lines is'
                       ' %d, in frame #%d' % (distance.distance,
                                              distance.frame.index)])

    if not frame_index_to_changed_files: # pragma: no cover
      logging.warning('Found no changed files for suspect: %s', str(suspect))
      return []

    # Sort changed file by frame index.
    _, changed_files = zip(*sorted(frame_index_to_changed_files.iteritems(),
                                   key=lambda x: x[0]))

    return list(changed_files)
