# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
from collections import namedtuple
import logging
import math

from analysis import crash_util
from analysis.crash_match import CrashedFile
from analysis.linear.changelist_features.min_distance import MinDistanceFeature
from analysis.linear.changelist_features.top_frame_index import (
    TopFrameIndexFeature)
from analysis.linear.changelist_features.touch_crashed_file import (
    TouchCrashedFileFeature)
from analysis.linear.feature import ChangedFile
from analysis.linear.feature import MetaFeature
from analysis.linear.feature import MetaFeatureValue
from analysis.linear.feature import LogLinearlyScaled
import libs.math.logarithms as lmath


class TouchCrashedFileMetaFeature(MetaFeature):
  """MetaFeature that wraps three ``Feature``s.

  This feature returns ``MetaFeatureValue``, which wraps the ``FeatureValue``s
  of ``MinDistanceFeature``, ``TopFrameIndexFeature`` and
  ``TouchCrashedFileFeature``.
  """

  def __init__(self, features, include_renamed_paths=False):
    """
    Args:
      features (list of ``Feature``): List of features relating to a touched
        file from the crash stacktrace, for example ``MinDistanceFeature``,
        ``TopFrameIndexFeature``.
      include_renamed_paths (boolean): Whether to also check for matches against
        the old file path when a file has been renamed.
    """
    super(TouchCrashedFileMetaFeature, self).__init__({
        feature.name: feature for feature in features})
    self._include_renamed_paths = include_renamed_paths

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
    paths = [touched_file.new_path]
    if self._include_renamed_paths:
      paths.append(touched_file.old_path)
    return any(crash_util.IsSameFilePath(crashed_file.value, path)
               for path in paths)

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
