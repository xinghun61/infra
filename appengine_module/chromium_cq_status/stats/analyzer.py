# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from itertools import chain
import re

from appengine_module.chromium_cq_status.model.cq_stats import CountStats, ListStats  # pylint: disable=C0301

class Analyzer(object):
  def new_patchset_attempts(self, issue, patchset, attempts):
    raise NotImplementedError()

  def build_stats(self):
    raise NotImplementedError()

  def _get_name(self):  # pragma: no cover
    return re.sub(r'([a-z])([A-Z])', r'\1_\2', type(self).__name__).lower()


class CountAnalyzer(Analyzer): # pylint: disable-msg=W0223
  def __init__(self):  # pragma: no cover
    self.count = 0

  def build_stats(self):  # pragma: no cover
    return (CountStats(
      name=self._get_name(),
      description=self.description,
      count=self.count,
    ),)


class ListAnalyzer(Analyzer): # pylint: disable-msg=W0223
  def __init__(self):  # pragma: no cover
    self.points = []
    self.lower_is_better = True

  def build_stats(self):  # pragma: no cover
    list_stats = ListStats(
      name=self._get_name(),
      description=self.description,
      unit=self.unit,
    )
    list_stats.set_from_points(self.points, self.lower_is_better)
    return (list_stats,)


class AnalyzerGroup(Analyzer):
  def __init__(self, *analyzer_classes):  # pragma: no cover
    self.analyzers = [cls() for cls in analyzer_classes]

  def new_patchset_attempts(self, issue, patchset, attempts): # pragma: no cover
    for analyzer in self.analyzers:
      analyzer.new_patchset_attempts(issue, patchset, attempts)

  def build_stats(self):  # pragma: no cover
    return chain(*(analyzer.build_stats() for analyzer in self.analyzers))
