# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import math
import os

from analysis.linear.feature import Feature
from analysis.linear.feature import FeatureValue
from analysis.linear.feature import LinearlyScaled

_MINIMUM_FILES = 15
_MAXIMUM_FILES = 45


class NumberOfTouchedFilesFeature(Feature):
  """Returns negative values if a suspect changes too many files.

  There are 3 range of values according to number of files a suspect changed:
  n <= self._minimum_files: 0.0
  self._minimum_files < n < self._maximum_files: (0.0, 1)
  self._maximum_files <= n: 1.0
  """
  def __init__(self, minimum_files=None, maximum_files=None):
    self._minimum_files = minimum_files or _MINIMUM_FILES
    self._maximum_files = maximum_files or _MAXIMUM_FILES

  @property
  def name(self):
    return 'NumberOfTouchedFiles'

  def __call__(self, report):
    """
    Args:
      report (CrashReport): the crash report being analyzed.

    Returns:
      A ``FeatureValue`` with name, log-domain value, reason and changed_files.
    """
    def FeatureValueGivenReport(suspect):  # pylint: disable=W0613
      """Compute ``FeatureValue`` for a suspect.

      Args:
        suspect (Suspect): The suspected changelog and some meta information
          about it.

      Returns:
        The ``FeatureValue`` of this feature.
      """

      number_of_files = len(suspect.changelog.touched_files)
      return FeatureValue(
          name=self.name,
          value=LinearlyScaled(number_of_files, self._maximum_files,
                               self._minimum_files, offset=-1.0),
          reason=None,
          changed_files=None)

    return FeatureValueGivenReport
