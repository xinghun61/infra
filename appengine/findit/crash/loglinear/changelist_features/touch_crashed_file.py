# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import math

from crash.loglinear.feature import Feature
from crash.loglinear.feature import FeatureValue


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
      report (CrashReport): the crash report being analyzed.

    Returns:
      A ``FeatureValue`` with name, log-domain value, reason and changed_files.
    """
    def FeatureValueGivenReport(suspect, matches):  # pylint: disable=W0613
      """Compute ``FeatureValue`` for a suspect.

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
                            value=0.0,
                            reason=None,
                            changed_files=None)

      return FeatureValue(
          name=self.name,
          value=1.0,
          reason='Touched files - %s' % ', '.join([
              touched_file.new_path
              for match in matches.itervalues()
              for touched_file in match.touched_files]),
          changed_files=None)

    return FeatureValueGivenReport
