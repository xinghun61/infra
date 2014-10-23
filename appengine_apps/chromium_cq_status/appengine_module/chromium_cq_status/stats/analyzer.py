# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
from itertools import chain
import re

from appengine_module.chromium_cq_status.model.cq_stats import (
  CountStats,
  ListStats,
)

class Analyzer(object):
  def new_attempts(self, attempts, reference, project):
    raise NotImplementedError()

  def build_stats(self):
    raise NotImplementedError()


class CountAnalyzer(Analyzer): # pylint: disable-msg=W0223
  def __init__(self):  # pragma: no cover
    self.tally = defaultdict(lambda: 0)

  def build_stats(self):  # pragma: no cover
    count_stats = CountStats(
      name=self._get_name(),
      description=self.description,
    )
    count_stats.set_from_tally(self.tally)
    return (count_stats,)

  def _get_name(self):  # pragma: no cover
    return dashed_class_name(self)


class ListAnalyzer(Analyzer): # pylint: disable-msg=W0223
  def __init__(self):  # pragma: no cover
    self.points = []

  def build_stats(self):  # pragma: no cover
    list_stats = ListStats(
      name=self._get_name(),
      description=self.description,
      unit=self.unit,
    )
    list_stats.set_from_points(self.points)
    return (list_stats,)

  def _get_name(self):  # pragma: no cover
    return dashed_class_name(self)


class AnalyzerGroup(Analyzer):
  def __init__(self, *analyzer_classes):  # pragma: no cover
    self.analyzers = [cls() for cls in analyzer_classes]

  def new_attempts(self, attempts, reference, project): # pragma: no cover
    for analyzer in self.analyzers:
      analyzer.new_attempts(attempts, reference, project)

  def build_stats(self):  # pragma: no cover
    return chain(*(analyzer.build_stats() for analyzer in self.analyzers))

def dashed_class_name(obj):  # pragma: no cover
  return re.sub(r'([a-z])([A-Z])', r'\1-\2', type(obj).__name__).lower()
