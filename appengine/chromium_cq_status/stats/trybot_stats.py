# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict, namedtuple
from itertools import chain

from shared.config import TRYJOBVERIFIER
from stats.analyzer import (
  Analyzer,
  CountAnalyzer,
)

tryjob_update_action = 'verifier_jobs_update'
tryjob_pass_status = 'JOB_SUCCEEDED'
tryjob_fail_status = 'JOB_FAILED'

TrybotReference = namedtuple('TrybotReference', 'master builder')

class TrybotAnalyzer(Analyzer):  # pragma: no cover
  def __init__(self):
    self.false_rejects = {'total': TrybotFalseRejectCount(None)}
    self.passes = {'total': TrybotPassCount(None)}
    self.failures = {'total': TrybotFailCount(None)}

  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    # counts maps from (master, builder) to [pass count, fail count].
    counts = defaultdict(lambda: [0, 0])
    # Cache successful builders across all attempts. CQ will reuse
    # successful builds from older attempts, but will still report it
    # in every attempt; do not count them more than once.
    succeeded_builders = set()
    for attempt in interval_attempts:
      # Cache failed builders within each attempt. CQ ignores failed
      # builds from prior attempts, but may report a failure more than
      # once within an attempt.
      failed_builders = set()
      for record in attempt:
        if record.fields.get('verifier') != TRYJOBVERIFIER:
          continue
        if record.fields.get('action') != tryjob_update_action:
          continue
        for job_result, builds in record.fields.get('jobs', {}).iteritems():
          if job_result not in [tryjob_pass_status, tryjob_fail_status]:
            continue
          for build in builds:
            count_builder = (build.get('master'), build.get('builder'))
            if count_builder in failed_builders.union(succeeded_builders):
              continue
            if job_result == tryjob_pass_status:
              count_key = 0
              succeeded_builders.add(count_builder)
            else:
              count_key = 1
              failed_builders.add(count_builder)
            counts[count_builder][count_key] += 1

    for (master, builder), (pass_count, fail_count) in counts.iteritems():
      if (master, builder) not in self.false_rejects:
        self.false_rejects[(master, builder)] = TrybotFalseRejectCount(builder)
      if (master, builder) not in self.passes:
        self.passes[(master, builder)] = TrybotPassCount(builder)
      if (master, builder) not in self.failures:
        self.failures[(master, builder)] = TrybotFailCount(builder)

      trybotReference = TrybotReference(master, builder)
      self.passes[(master, builder)].tally[reference] += pass_count
      self.passes['total'].tally[trybotReference] += pass_count
      self.failures[(master, builder)].tally[reference] += fail_count
      self.failures['total'].tally[trybotReference] += fail_count
      if pass_count > 0 and fail_count > 0:
        self.false_rejects[(master, builder)].tally[reference] += fail_count
        self.false_rejects['total'].tally[trybotReference] += fail_count

  def build_stats(self):
    stats = []
    analyzers = chain(
        self.false_rejects.itervalues(),
        self.passes.itervalues(),
        self.failures.itervalues())
    for analyzer in analyzers:
      stats.extend(analyzer.build_stats())
    return stats

class TrybotFalseRejectCount(CountAnalyzer):  # pragma: no cover
  # pylint: disable=W0223
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
  # pylint: disable=W0223
  def __init__(self, builder):
    super(TrybotPassCount, self).__init__()
    trybot = ('by the %s trybot' % builder) if builder else 'across all trybots'
    self.description = 'Number of passing runs %s.' % trybot
    self.builder = builder

  def _get_name(self):
    if self.builder:
      return 'trybot-%s-pass-count' % self.builder
    return 'trybot-pass-count'

class TrybotFailCount(CountAnalyzer):  # pragma: no cover
  # pylint: disable=W0223
  def __init__(self, builder):
    super(TrybotFailCount, self).__init__()
    trybot = ('by the %s trybot' % builder) if builder else 'across all trybots'
    self.description = 'Number of failing runs %s.' % trybot
    self.builder = builder

  def _get_name(self):
    if self.builder:
      return 'trybot-%s-fail-count' % self.builder
    return 'trybot-fail-count'
