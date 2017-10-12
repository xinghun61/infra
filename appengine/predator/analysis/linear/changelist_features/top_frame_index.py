# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from analysis.linear.feature import Feature
from analysis.linear.feature import FeatureValue
from analysis.linear.feature import LinearlyScaled

_MINIMUM_FEATURE_VALUE = 0
_DEFAULT_MAX_FRAME_INDEX = 7


class TopFrameIndexFeature(Feature):
  """Returns the minimum frame index scaled between 0 and 1.

  If a suspect touched crashed files in stacktrace, the closer the touched frame
  is to the signature frame(top frame), the more likely the suspect is the
  culprit.
  ``TopFrameIndexFeature`` emphasizes signature frame and frames near it.
  """
  def __init__(self, max_frame_index=_DEFAULT_MAX_FRAME_INDEX):
    """
    Args:
      max_frame_index (int): An upper bound on the minimum frame index
        to consider.
    """
    self.max_frame_index = max_frame_index

  @property
  def name(self):
    return 'TopFrameIndex'

  def __call__(self, report):
    """The minimum ``StackFrame.index`` across all files and stacks.

    Args:
      report (CrashReport): the crash report being analyzed.

    Returns:
      A function from ``Suspect`` to the scaled minimum frame index, as a
      log-domain ``float``.
    """
    def FeatureValueGivenReport(suspect, matches):  # pylint: disable=W0613
      """Computes ``FeatureValue`` for a suspect.

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
        return FeatureValue(name=self.name,
                            value=0,
                            reason=None,
                            changed_files=None)

      def TopFrameInMatches(matches):
        frames = [frame_info.frame for match in matches.itervalues()
                  for frame_info in match.frame_infos]
        frames.sort(key=lambda frame: frame.index)
        return frames[0]

      top_frame = TopFrameInMatches(matches)
      value = LinearlyScaled(float(top_frame.index),
                             float(self.max_frame_index))

      # This feature reason is redundant to MinDistance or TouchedCrashedFile
      # features, which also mentioned which files the suspected cl touched with
      # more useful information. So the reason for this feature is not very
      # helpful, we are not providing the reason for this feature.
      return FeatureValue(self.name, value, None, None)

    return FeatureValueGivenReport
