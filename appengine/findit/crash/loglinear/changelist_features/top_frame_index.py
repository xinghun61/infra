# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from crash.loglinear.feature import Feature
from crash.loglinear.feature import FeatureValue
from crash.loglinear.feature import LogLinearlyScaled
import libs.math.logarithms as lmath


class TopFrameIndexFeature(Feature):
  """Returns the minimum frame index scaled between -inf and 0.

  That is, the normal-domain value is scaled linearly between 0 and 1,
  but since we want to return a log-domain value we take the logarithm
  of that (hence -inf to 0). This ensures that when a suspect has a
  linearly-scaled value of 0 (aka log-scaled value of -inf) we absolutely
  refuse to blame that suspect. This heuristic behavior is intended. Before
  changing it to be less aggressive about refusing to blame the suspect,
  we should delta test to be sure the new heuristic acts as indented.

  When the actual minimum frame index is zero, we return the log-domain
  value 0 (aka normal-domain value of 1). When the suspect has no frames or
  the actual minimum frame index is greater than the ``max_frame_index``,
  we return the log-domain value -inf (aka normal-domain value of 0). In
  between we scale the normal-domain values linearly, which means the
  log-domain values are scaled exponentially.
  """
  def __init__(self, max_frame_index):
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
      report (CrashReportWithDependencies): the crash report being analyzed.

    Returns:
      A function from ``Suspect`` to the scaled minimum frame index, as a
      log-domain ``float``.
    """
    def FeatureValueGivenReport(
        suspect, touched_file_to_stack_infos):  # pylint: disable=W0613
      """Computes ``FeatureValue`` for a suspect.

      Args:
        suspect (Suspect): The suspected changelog and some meta information
          about it.
        touched_file_to_stack_infos(dict): Dict mapping ``FileChangeInfo`` to
          a list of ``StackInfo``s representing all the frames that the suspect
          touched.

      Returns:
        The ``FeatureValue`` of this feature.
      """
      if not touched_file_to_stack_infos:
        return FeatureValue(
            self.name, lmath.LOG_ZERO,
            'No frame got touched by the suspect.', None)

      def TopFrameIndexForTouchedFile(stack_infos):
        return min([stack_info.frame.index for stack_info in stack_infos])

      top_frame_index = min([
          TopFrameIndexForTouchedFile(stack_infos) for _, stack_infos in
          touched_file_to_stack_infos.iteritems()])

      return FeatureValue(
          name = self.name,
          value = LogLinearlyScaled(float(top_frame_index),
                                    float(self.max_frame_index)),
          reason = ('Top frame is #%d' % top_frame_index),
          changed_files = None)

    return FeatureValueGivenReport
