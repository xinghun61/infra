# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
from collections import namedtuple
import logging
import math

from crash import crash_util
from crash.crash_match import CrashedGroup
from crash.loglinear.changelist_features.min_distance import MinDistanceFeature
from crash.loglinear.changelist_features.top_frame_index import (
    TopFrameIndexFeature)
from crash.loglinear.changelist_features.touch_crashed_file import (
    TouchCrashedFileFeature)
from crash.loglinear.feature import ChangedFile
from crash.loglinear.feature import MetaFeature
from crash.loglinear.feature import MetaFeatureValue
from crash.loglinear.feature import LogLinearlyScaled
import libs.math.logarithms as lmath

# N.B., this must not be infinity, else we'll start getting NaN values
# from LinearMinDistanceFeature (and SquaredMinDistanceFeature).
DEFAULT_MAX_LINE_DISTANCE = 50
DEFAULT_MAX_FRAME_INDEX = 7


class CrashedFile(CrashedGroup):
  """Represents a crashed file in stacktrace."""
  pass


class TouchCrashedFileMetaFeature(MetaFeature):
  """MetaFeature that wraps three ``Feature``s.

  This feature returns ``MetaFeatureValue``, which wraps the ``FeatureValue``s
  of ``MinDistanceFeature``, ``TopFrameIndexFeature`` and
  ``TouchCrashedFileFeature``.
  """

  def __init__(self, get_repository,
               max_line_distance=DEFAULT_MAX_LINE_DISTANCE,
               max_frame_index=DEFAULT_MAX_FRAME_INDEX):
    """
    Args:
      get_repository (callable): a function from DEP urls to ``Repository``
        objects, so we can get changelogs and blame for each dep. Notably,
        to keep the code here generic, we make no assumptions about
        which subclass of ``Repository`` this function returns. Thus,
        it is up to the caller to decide what class to return and handle
        any other arguments that class may require (e.g., an http client
        for ``GitilesRepository``).
        This factory is needed because the ``MinDistanceFeature`` in this meta
        feature needs to get blame for files touched by suspect.
      max_line_distance (int): An upper bound on the min_distance to
        consider. This argument is optional and defaults to
        ``DEFAULT_MAX_LINE_DISTANCE``.
      max_frame_index (int): An upper bound on the minimum frame index
        to consider. This argument is optional and defaults to
        ``DEFAULT_MAX_FRAME_INDEX``.
    """
    min_distance_feature = MinDistanceFeature(get_repository, max_line_distance)
    top_frame_index_feature = TopFrameIndexFeature(max_frame_index)
    touch_crashed_file_feature = TouchCrashedFileFeature()

    super(TouchCrashedFileMetaFeature, self).__init__({
        min_distance_feature.name: min_distance_feature,
        top_frame_index_feature.name: top_frame_index_feature,
        touch_crashed_file_feature.name: touch_crashed_file_feature
    })

  def CrashedGroupFactory(self, frame):
    """Factory function to create ``CrashedFile``."""
    return CrashedFile(frame.file_path) if frame.file_path else None

  def Match(self, crashed_file, touched_file):
    """Determines whether a touched_file matches this crashed file or not.

    Args:
      touched_file (FileChangeInfo): touched file to examine.

    Returns:
      Boolean indicating whether it is a match or not.
    """
    return crash_util.IsSameFilePath(crashed_file.value, touched_file.new_path)

  @property
  def name(self):
    return 'TouchCrashedFileMeta'

  def __call__(self, report):
    """Returns a function mapping suspect to its ``MetaFeatureValue``.

    Args:
      report (CrashReportWithDependensies): the crash report being analyzed.

    Returns:
      A function from ``Suspect`` to ``MetaFeatureValue``, ``MetaFeatureValue``
      wraps ``FeatureValue`` of "MinDistance" (the minimum distance between the
      stacktrace and the suspect, as a log-domain ``float``), ``FeatureValue``
      of "TopFrameIndex" (the top frame index of the stack frame touched by
      the suspect, as a log-domain ``float``.) and ``FeatureValue`` of
      "TouchCrashedFileFeature" (whether this suspect touched file or not)
    """
    # Preprocessing stacktrace and dependencies to get crashed file information
    # about the frames and callstack priority of that crashed file in
    # stacktrace.
    dep_to_grouped_frame_infos = crash_util.IndexFramesWithCrashedGroup(
        report.stacktrace, self.CrashedGroupFactory, report.dependencies)
    features_given_report = {name: feature(report)
                             for name, feature in self.iteritems()}

    def FeatureValueGivenReport(suspect):
      """Function mapping suspect related data to its FeatureValue.

      Args:
        suspect (Suspect): The suspected changelog and some meta information
          about it.
        touched_file_to_stack_infos(dict): Dict mapping ``FileChangeInfo`` to
          a list of ``StackInfo``s representing all the frames that the suspect
          touched.

      Returns:
        The ``FeatureValue`` of this feature.
      """
      grouped_frame_infos = dep_to_grouped_frame_infos.get(suspect.dep_path, {})
      matches = crash_util.MatchSuspectWithFrameInfos(suspect,
                                                      grouped_frame_infos,
                                                      self.Match)

      return MetaFeatureValue(
          self.name, {name: fx(suspect, matches)
                      for name, fx in features_given_report.iteritems()})

    return FeatureValueGivenReport
