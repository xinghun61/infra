# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from crash.loglinear.feature import Feature
from crash.loglinear.feature import FeatureValue
from crash.loglinear.feature import LogLinearlyScaled
import libs.math.logarithms as lmath

# TODO(katesonia): Move this to the config saved in datastore.
_MAX_FRAME_INDEX = 7


class TopFrameIndexFeature(Feature):
  """Returns the minimum frame index scaled between -inf and 0.

  That is, the normal-domain value is scaled linearly between 0 and 1,
  but since we want to return a log-domain value we take the logarithm
  of that (hence -inf to 0). This ensures that when a result has a
  linearly-scaled value of 0 (aka log-scaled value of -inf) we absolutely
  refuse to blame that result. This heuristic behavior is intended. Before
  changing it to be less aggressive about refusing to blame the result,
  we should delta test to be sure the new heuristic acts as indented.

  When the actual minimum frame index is zero, we return the log-domain
  value 0 (aka normal-domain value of 1). When the result has no frames or
  the actual minimum frame index is greater than the ``max_frame_index``,
  we return the log-domain value -inf (aka normal-domain value of 0). In
  between we scale the normal-domain values linearly, which means the
  log-domain values are scaled exponentially.
  """
  def __init__(self, max_frame_index=None):
    """
    Args:
      max_frame_index (int): An upper bound on the minimum frame index
        to consider. This argument is optional and defaults to
        ``_MAX_FRAME_INDEX``.
    """
    if max_frame_index is None:
      max_frame_index = _MAX_FRAME_INDEX
    self.max_frame_index = max_frame_index

  @property
  def name(self):
    return "TopFrameIndex"

  def __call__(self, report):
    """The minimum ``StackFrame.index`` across all files and stacks.

    Args:
      report (CrashReport): the crash report being analyzed.

    Returns:
      A function from ``Result`` to the scaled minimum frame index, as a
      log-domain ``float``.
    """
    def FeatureValueGivenReport(result):
      if not result.file_to_stack_infos:
        logging.warning('No StackInfo for any file: %s' % str(result))
        return FeatureValue(self.name, lmath.LOG_ZERO,
            "No StackInfo for any file", None)

      top_frame_index = min(min(frame.index for frame, _ in stack_infos)
                            for stack_infos
                            in result.file_to_stack_infos.itervalues())
      return FeatureValue(
          name = self.name,
          value = LogLinearlyScaled(float(top_frame_index),
                                    float(self.max_frame_index)),
          reason = ('Top frame is #%d' % top_frame_index),
          changed_files = None)

    return FeatureValueGivenReport
