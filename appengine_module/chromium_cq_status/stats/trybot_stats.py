# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict, namedtuple

from appengine_module.chromium_cq_status.shared.config import TRYJOBVERIFIER
from appengine_module.chromium_cq_status.stats.analyzer import (
  Analyzer,
  CountAnalyzer,
)

tryjob_update_action = 'verifier_jobs_update'
tryjob_pass_status = 0
tryjob_fail_status = 1

TrybotReference = namedtuple('TrybotReference', 'master builder')

class TrybotAnalyzer(Analyzer):  # pragma: no cover
  def __init__(self):
    self.false_rejects = {'total': TrybotFalseRejectCount(None)}
    self.passes = {'total': TrybotPassCount(None)}

  def new_attempts(self, attempts, reference):
    # counts maps from (master, builder) to [pass count, fail count].
    counts = defaultdict(lambda: [0, 0])

    for attempt in attempts:
      for record in attempt:
        if record.fields.get('verifier') != TRYJOBVERIFIER:
          continue
        if record.fields.get('action') != tryjob_update_action:
          continue
        for master in record.fields.get('jobs', ()):
          for builder in record.fields['jobs'][master]:
            build = record.fields['jobs'][master][builder]
            if build.get('status') == tryjob_pass_status:
              counts[(master, builder)][0] += 1
            elif build.get('status') == tryjob_fail_status:
              counts[(master, builder)][1] += 1

    for (master, builder), (pass_count, fail_count) in counts.iteritems():
      if (master, builder) not in self.false_rejects:
        self.false_rejects[(master, builder)] = TrybotFalseRejectCount(builder)
      if (master, builder) not in self.passes:
        self.passes[(master, builder)] = TrybotPassCount(builder)

      trybotReference = TrybotReference(master, builder)
      self.passes[(master, builder)].tally[reference] += pass_count
      self.passes['total'].tally[trybotReference] += pass_count
      if pass_count > 0 and fail_count > 0:
        self.false_rejects[(master, builder)].tally[reference] += fail_count
        self.false_rejects['total'].tally[trybotReference] += fail_count

  def build_stats(self):
    stats = []
    for analyzer in self.false_rejects.values() + self.passes.values():
      stats.extend(analyzer.build_stats())
    return stats

class TrybotFalseRejectCount(CountAnalyzer):  # pragma: no cover
  # pylint: disable-msg=W0223
  def __init__(self, builder):
    super(TrybotFalseRejectCount, self).__init__()
    trybot = 'by the %s trybot' % builder if builder else 'across all trybots'
    self.description = ('Number of false rejects %s. This counts any failed '
                        'runs that also had passing runs on the same patch.' %
                        trybot)
    self.builder = builder

  def _get_name(self):
    if self.builder:
      return 'trybot-%s-false-reject-count' % self.builder
    return 'trybot-false-reject-count'

class TrybotPassCount(CountAnalyzer):  # pragma: no cover
  # pylint: disable-msg=W0223
  def __init__(self, builder):
    super(TrybotPassCount, self).__init__()
    trybot = 'by the %s trybot' % builder if builder else 'across all trybots'
    self.description = 'Number of passing runs %s.' % trybot
    self.builder = builder

  def _get_name(self):
    if self.builder:
      return 'trybot-%s-pass-count' % self.builder
    return 'trybot-pass-count'
