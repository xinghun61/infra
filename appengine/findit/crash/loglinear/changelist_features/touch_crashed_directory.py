# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
from collections import namedtuple
import logging
import math
import os

from crash import crash_util
from crash.loglinear.feature import Feature
from crash.loglinear.feature import FeatureValue
import libs.math.logarithms as lmath


class CrashedDirectory(namedtuple('CrashedDirectory', ['value'])):
  """Represents a crashed directory.

  ``CrashedDirectory`` is a crashed group which knows whether itself matches a
  touched file(``FileChangeIno``) or not.
  """
  __slots__ = ()

  def MatchTouchedFile(self, touched_file):
    """Determines whether a touched_file matches this crashed directory or not.

    Args:
      touched_file (FileChangeInfo): touched file to examine.

    Returns:
      Boolean indicating whether it is a match or not.
    """
    touched_dir = (os.path.dirname(touched_file.new_path)
                   if touched_file.new_path else None)
    return crash_util.IsSameFilePath(self.value, touched_dir)

  def __str__(self):  # pragma: no cover
    return '%s(value = %s)' % (self.__class__.__name__, self.value)


class TouchCrashedDirectoryFeature(Feature):
  """Returns either log one or log zero.

  When a suspect touched crashed file, we return the log-domain
  value 0 (aka normal-domain value of 1). When the there is no file match,
  we return log-domain value -inf (aka normal-domain value of 0).
  """
  @property
  def name(self):
    return 'TouchCrashedDirectory'

  def CrashedDirectoryFactory(self, frame):
    """Factory function to create ``CrashedDirectory``."""
    return CrashedDirectory(os.path.dirname(frame.file_path) if frame else None)

  def __call__(self, report):
    """
    Args:
      report (CrashReport): the crash report being analyzed.

    Returns:
      A ``FeatureValue`` with name, log-domain value, reason and changed_files.
    """
    dep_to_grouped_frame_infos = crash_util.IndexFramesWithCrashedGroup(
        report.stacktrace, self.CrashedDirectoryFactory, report.dependencies)

    def FeatureValueGivenReport(suspect):  # pylint: disable=W0613
      """Compute ``FeatureValue`` for a suspect.

      Args:
        suspect (Suspect): The suspected changelog and some meta information
          about it.

      Returns:
        The ``FeatureValue`` of this feature.
      """
      grouped_frame_infos = dep_to_grouped_frame_infos.get(suspect.dep_path, {})
      matches = crash_util.MatchSuspectWithFrameInfos(suspect,
                                                      grouped_frame_infos)

      if not matches:
        return FeatureValue(name=self.name,
                            value=0.0,
                            reason=None,
                            changed_files=None)

      def _ReasonForCrashMatch(match):
        frame_file_path_to_index = defaultdict(list)
        for frame_info in match.frame_infos:
          frame_file_path_to_index[
              frame_info.frame.file_path].append(frame_info.frame.index)

        frame_file_path_to_index = {
            file_path: ', '.join(['frame#%d' % indice for indice in index])
            for file_path, index in frame_file_path_to_index.iteritems()
        }
        return (
            'Changed files %s, which are under the same directory %s as %s') % (
                ', '.join([touched_file.new_path
                           for touched_file in match.touched_files]),
                match.crashed_group.value,
                ', '.join(['%s (in %s)' % (file_path, index)
                           for file_path, index in
                           frame_file_path_to_index.iteritems()]))

      return FeatureValue(
          name=self.name,
          value=1.0,
          reason='\n'.join([_ReasonForCrashMatch(match)
                            for match in matches.itervalues()]),
          changed_files=None)

    return FeatureValueGivenReport
