# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""TopFrameIndex scorer applies to all Result objects.

It represents a heuristic rule:
  The less the top frame index (this result changed) is, the higher score.
"""

from crash.scorers.scorer import Scorer

# TODO(katesonia): Move this to the config saved in datastore.
_MAX_TOP_N_FRAMES = 7
_INFINITY = 1000


class TopFrameIndex(Scorer):

  def __init__(self, max_top_n=_MAX_TOP_N_FRAMES):
    self.max_top_n = max_top_n

  def GetMetric(self, result):
    if not result.file_to_stack_infos:
      return None

    top_frame_index = _INFINITY
    for _, stack_infos in result.file_to_stack_infos.iteritems():
      for frame, _ in stack_infos:
        top_frame_index = min(top_frame_index, frame.index)

    return top_frame_index

  def Score(self, top_frame_index):
    # TODO(katesonia): experiment the model and parameters later.
    if top_frame_index < self.max_top_n:
      return 1 - top_frame_index / float(self.max_top_n)

    return 0

  def Reason(self, top_frame_index, score):
    if score == 0:
      return ''

    return 'Modified top crashing frame is #%d' % top_frame_index
