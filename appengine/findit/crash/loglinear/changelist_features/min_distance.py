# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import math

from crash.loglinear.feature import ChangedFile
from crash.loglinear.feature import Feature
from crash.loglinear.feature import FeatureValue
from crash.loglinear.feature import LogLinearlyScaled
import libs.math.logarithms as lmath

# N.B., this must not be infinity, else we'll start getting NaN values
# from LinearMinDistanceFeature (and SquaredMinDistanceFeature).
DEFAULT_MAXIMUM = 50


class MinDistanceFeature(Feature):
  """Returns the minimum min_distance scaled between -inf and 0.

  That is, the normal-domain value is scaled linearly between 0 and 1,
  but since we want to return a log-domain value we take the logarithm
  of that (hence -inf to 0). This ensures that when a suspect has a
  linearly-scaled value of 0 (aka log-scaled value of -inf) we absolutely
  refuse to blame that suspect. This heuristic behavior is intended. Before
  changing it to be less aggressive about refusing to blame the suspect,
  we should delta test to be sure the new heuristic acts as indented.

  When the actual minimum min_distance is zero, we return the log-domain
  value 0 (aka normal-domain value of 1). When the suspect has no files
  or the actual minimum min_distance is greater than the ``maximum``,
  we return the log-domain value -inf (aka normal-domain value of 0). In
  between we scale the normal-domain values linearly, which means the
  log-domain values are scaled exponentially.
  """
  def __init__(self, maximum=None):
    """
    Args:
      maximum (float): An upper bound on the min_distance to
        consider. This argument is optional and defaults to
        ``DEFAULT_MAXIMUM``.
    """
    if maximum is None:
      maximum = DEFAULT_MAXIMUM
    self._maximum = maximum

  @property
  def name(self):
    return 'MinDistance'

  def __call__(self, report):
    """Returns the scaled min ``AnalysisInfo.min_distance`` across all files.

    Args:
      report (CrashReport): the crash report being analyzed.

    Returns:
      A function from ``Suspect`` to the minimum distance between (the code
      for) a stack frame in that suspect and the CL in that suspect, as a
      log-domain ``float``.
    """
    def FeatureValueGivenReport(suspect):
      analyses = suspect.file_to_analysis_info
      if not analyses:
        message = 'No AnalysisInfo for any file in suspect: %s' % str(suspect)
        logging.warning(message)
        return FeatureValue(self.name, lmath.LOG_ZERO, message, None)

      min_distance = min(per_file_analysis.min_distance
                         for per_file_analysis in analyses.itervalues())

      return FeatureValue(
          name = self.name,
          value = LogLinearlyScaled(float(min_distance), float(self._maximum)),
          reason = ('Minimum distance is %d' % min_distance),
          changed_files = self._ChangedFiles(suspect),
      )

    return FeatureValueGivenReport

  def _ChangedFiles(self, suspect):
    """Get all the changed files causing this feature to blame this suspect.

    Arg:
      suspect (Suspect): the suspect being blamed.

    Returns:
      List of ``ChangedFile`` objects sorted by frame index. For example:

        [ChangedFile(
            file = 'render_frame_impl.cc',
            blame_url = 'https://chr.com/../render_frame_impl.cc#1586',
            reasons = ['Minimum distance (LOC) 1, frame #5']
        )]
    """
    index_to_changed_files = {}

    for file_path, analysis_info in suspect.file_to_analysis_info.iteritems():
      file_name = file_path.split('/')[-1]
      frame = analysis_info.min_distance_frame
      if frame is None: # pragma: no cover
        logging.warning('Missing the min_distance_frame for %s'
            % str(analysis_info))
        continue

      # It is possible that a changelog doesn't show in the blame of a file,
      # in this case, treat the changelog as if it didn't change the file.
      if math.isinf(analysis_info.min_distance): # pragma: no cover
        logging.warning('min_distance is infinite for %s' % str(analysis_info))
        continue

      index_to_changed_files[frame.index] = ChangedFile(
          name = file_name,
          blame_url = frame.BlameUrl(suspect.changelog.revision),
          reasons = ['Minimum distance (LOC) %d, frame #%d' % (
              analysis_info.min_distance, frame.index)]
      )

    if not index_to_changed_files: # pragma: no cover
      logging.warning('Found no changed files for suspect: %s', str(suspect))

    # Sort changed file by frame index.
    _, changed_files = zip(*sorted(index_to_changed_files.items(),
                                   key=lambda x: x[0]))

    return list(changed_files)
