# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""MinDistance scorer applies to MatchResult objects.

It represents a heuristic rule:
  1. Highest score if the result changed the crashed lines.
  2. 0 score if changed lines are too far away from crashed lines.
"""

import logging

from crash.scorers.scorer import Scorer

_MAX_DISTANCE = 50


class MinDistance(Scorer):

  def __init__(self, max_distance=_MAX_DISTANCE):
    self.max_distance = max_distance

  def GetMetric(self, result):
    min_distance = float('inf')
    for analysis_info in result.file_to_analysis_info.itervalues():
      min_distance = min(min_distance, analysis_info['min_distance'])

    return min_distance

  def Score(self, min_distance):
    if min_distance > self.max_distance:
      return 0

    if min_distance == 0:
      return 1

    # TODO(katesonia): This number is randomly picked from a reasonable range,
    # best value to use still needs be experimented out.
    return 0.8

  def Reason(self, min_distance, score):
    if score == 0:
      return None

    return self.name, score, 'Minimum distance is %d' % min_distance

  def ChangedFiles(self, result):
    index_to_changed_files = {}
    for file_path, analysis_info in result.file_to_analysis_info.iteritems():
      file_name = file_path.split('/')[-1]
      frame = analysis_info['min_distance_frame']
      index_to_changed_files[frame.index] = {
          'file': file_name,
          'blame_url': frame.BlameUrl(result.changelog.revision),
          'info': 'Minimum distance (LOC) %d, frame #%d' % (
              analysis_info['min_distance'], frame.index)
      }

    # Sort changed file by frame index.
    _, changed_files = zip(*sorted(index_to_changed_files.items(),
                                     key=lambda x: x[0]))

    return list(changed_files)
