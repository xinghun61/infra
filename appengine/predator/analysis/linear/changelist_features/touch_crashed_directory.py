# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
from collections import namedtuple
import logging
import math
import os
import re

from analysis import crash_util
from analysis.crash_match import CrashedDirectory
from analysis.linear.feature import Feature
from analysis.linear.feature import FeatureValue
from libs.gitiles.diff import ChangeType


class TouchCrashedDirectoryFeature(Feature):
  """Returns either one or zero.

  When a suspect touched crashed directory, we return the
  value 1. When the there is no directory match, we return value 0.
  """
  def __init__(self, include_test_files=True, options=None):
    """
    Args:
      include_test_files (boolean): If False, it makes the feature ignore test
        files that the suspect touched (e.g. unittest, browsertest, perftest).
    """
    self._include_test_files = include_test_files
    blacklist = options.get('blacklist', []) if options else []
    self._blacklist = [directory.lower() for directory in blacklist]

  @property
  def name(self):
    return 'TouchCrashedDirectory'

  def CrashedGroupFactory(self, frame):
    """Factory function to create ``CrashedDirectory``."""
    # Since files in root directory are files like OWNERS, DEPS. Skip it.
    directory = os.path.dirname(frame.file_path)
    if not directory or directory.lower() in self._blacklist:
      return None

    return CrashedDirectory(directory)

  def Match(self, crashed_directory, touched_file):
    """Determines whether a touched_file matches this crashed directory or not.

    Args:
      touched_file (FileChangeInfo): touched file to examine.

    Returns:
      Boolean indicating whether it is a match or not.
    """
    if touched_file.change_type == ChangeType.DELETE:
      return False

    if not self._include_test_files and _IsTestFile(touched_file.new_path):
      return False

    touched_dir = os.path.dirname(touched_file.new_path)
    return crash_util.IsSameFilePath(crashed_directory.value, touched_dir)

  def __call__(self, report):
    """
    Args:
      report (CrashReport): the crash report being analyzed.

    Returns:
      A ``FeatureValue`` with name, log-domain value, reason and changed_files.
    """
    dep_to_grouped_frame_infos = crash_util.IndexFramesWithCrashedGroup(
        report.stacktrace, self.CrashedGroupFactory, report.dependencies)

    def FeatureValueGivenReport(suspect):
      """Compute ``FeatureValue`` for a suspect.

      Args:
        suspect (Suspect): The suspected changelog and some meta information
          about it.

      Returns:
        The ``FeatureValue`` of this feature.
      """
      grouped_frame_infos = dep_to_grouped_frame_infos.get(suspect.dep_path, {})
      matches = crash_util.MatchSuspectWithFrameInfos(suspect,
                                                      grouped_frame_infos,
                                                      self.Match)

      if not matches:
        return FeatureValue(name=self.name,
                            value=0.0,
                            reason=None,
                            changed_files=None)

      crashed_directories = [directory.value for directory in matches]
      plural = len(crashed_directories) > 1

      reason = [
          'Suspected changelist touched file(s) in the %s %s, which '
          'appear%s in the stack trace.' % (
                'directories' if plural else 'directory',
                ', '.join(crashed_directories),
                '' if plural else 's')]

      return FeatureValue(
          name=self.name,
          value=1.0,
          reason=reason,
          changed_files=None)

    return FeatureValueGivenReport


def _IsTestFile(filename):
  regex = re.compile(
      r'(unittest|perftest|performancetest|browsertest|_test)\.[^/.]+$')
  return regex.search(filename) is not None
