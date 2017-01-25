# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import math

from crash.loglinear.feature import ChangedFile
from crash.loglinear.feature import Feature
from crash.loglinear.feature import FeatureValue
from crash.loglinear.feature import LogLinearlyScaled
import libs.math.logarithms as lmath


class TouchCrashedFileFeature(Feature):
  """Returns either log one or log zero.

  When a suspect touched crashed file, we return the log-domain
  value 0 (aka normal-domain value of 1). When the there is no file match,
  we return log-domain value -inf (aka normal-domain value of 0).
  """
  @property
  def name(self):
    return 'TouchCrashedFile'

  def __call__(self, report):
    """
    Args:
      report (CrashReportWithDependencies): the crash report being analyzed.

    Returns:
      A ``FeatureValue`` with name, log-domain value, reason and changed_files.
    """
    def FeatureValueGivenReport(
        suspect, touched_file_to_stack_infos):  # pylint: disable=W0613
      """Compute ``FeatureValue`` for a suspect.

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
            'No file got touched by the suspect.', None)

      return FeatureValue(
          name = self.name,
          value = lmath.LOG_ONE,
          reason = ('Touched files - %s' % ', '.join([
              touched_file.new_path for touched_file, _ in
              touched_file_to_stack_infos.iteritems()])),
          changed_files = None)

    return FeatureValueGivenReport
