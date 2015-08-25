# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import datetime
import sys

from infra.tools.cq_stats import cq_stats
from infra_libs import logs
from infra_libs import ts_mon


def parse_args(args):
  parser = argparse.ArgumentParser('python -m %s' % __package__)
  parser.add_argument('--project', required=True)
  parser.add_argument('--range', required=True)
  logs.add_argparse_options(parser)
  ts_mon.add_argparse_options(parser)

  parser.set_defaults(
      logs_directory='',
      ts_mon_target_type='task',
      ts_mon_task_service_name='cq_stats_uploader',
  )

  opts = parser.parse_args(args)

  if not opts.ts_mon_task_job_name:
    opts.ts_mon_task_job_name = '%s-%s' % (opts.project, opts.range)

  logs.process_argparse_options(opts)
  ts_mon.process_argparse_options(opts)

  return opts


class StatsArgs(object):
  def __init__(self, project, date_range):
    self.project = project
    self.range = date_range
    # TODO(phajdan.jr): Deduplicate this and cq_stats logic.
    self.date = (datetime.datetime.now() -
                 datetime.timedelta(minutes=cq_stats.INTERVALS[date_range]))
    self.use_logs = True
    self.seq = False
    self.thread_pool = 200


patchset_committed_durations = ts_mon.NonCumulativeDistributionMetric(
    'commit_queue/attempts/committed/durations')

attempt_false_reject_count = ts_mon.GaugeMetric(
    'commit_queue/attempts/cq_stats/false_reject_count')
attempt_count = ts_mon.GaugeMetric(
    'commit_queue/attempts/cq_stats/count')


def main(args):
  opts = parse_args(args)

  stats = cq_stats.acquire_stats(
      StatsArgs(opts.project, opts.range), add_tree_stats=False)

  try:
    durations_dist = ts_mon.Distribution(ts_mon.GeometricBucketer())
    for duration in stats['patchset-committed-durations']['raw']:
      durations_dist.add(duration)
    patchset_committed_durations.set(durations_dist)

    attempt_false_reject_count.set(stats['attempt-false-reject-count'])
    attempt_count.set(stats['attempt-count'])
  finally:
    ts_mon.flush()

  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
